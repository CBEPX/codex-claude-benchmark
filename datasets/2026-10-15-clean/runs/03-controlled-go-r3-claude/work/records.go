package records

import (
	"bufio"
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"strings"
)

type Record struct {
	ID    string `json:"id"`
	Value int    `json:"value"`
}

// ErrLineTooLong is returned when a line's content (without CR/LF) exceeds maxBytes.
var ErrLineTooLong = errors.New("records: line too long")

// ErrInvalidLimit is returned for a negative maxBytes.
var ErrInvalidLimit = errors.New("records: negative maxBytes")

// ReadUnique parses NDJSON records from r, skipping blank lines and keeping
// only the first record for each exact ID in order of appearance.
// maxBytes > 0 limits the length of each line's content excluding CR/LF;
// maxBytes == 0 means no limit. On any error it returns nil and the error.
func ReadUnique(r io.Reader, maxBytes int) ([]Record, error) {
	if maxBytes < 0 {
		return nil, ErrInvalidLimit
	}
	br := bufio.NewReader(r)
	out := []Record{}
	seen := make(map[string]struct{})
	for lineNo := 1; ; lineNo++ {
		line, err := readLine(br, maxBytes)
		if err != nil && !errors.Is(err, io.EOF) {
			return nil, fmt.Errorf("records: line %d: %w", lineNo, err)
		}
		eof := err != nil
		if len(bytes.TrimSpace(line)) > 0 {
			var v Record
			if uerr := json.Unmarshal(line, &v); uerr != nil {
				return nil, fmt.Errorf("records: line %d: invalid JSON: %w", lineNo, uerr)
			}
			if strings.TrimSpace(v.ID) == "" {
				return nil, fmt.Errorf("records: line %d: empty id", lineNo)
			}
			if _, dup := seen[v.ID]; !dup {
				seen[v.ID] = struct{}{}
				out = append(out, v)
			}
		}
		if eof {
			return out, nil
		}
	}
}

// readLine reads one line and returns its content without the trailing LF
// and an optional preceding CR. It returns io.EOF together with the final
// (possibly empty) line when the input ends. Any other read error is returned
// as is. If maxBytes > 0 and the content exceeds it, ErrLineTooLong is
// returned without buffering the rest of the line.
func readLine(br *bufio.Reader, maxBytes int) ([]byte, error) {
	var buf []byte
	for {
		chunk, err := br.ReadSlice('\n')
		buf = append(buf, chunk...)
		// Allow one extra byte for a possible trailing CR before LF.
		if maxBytes > 0 && contentLen(buf, err == nil) > maxBytes {
			return nil, ErrLineTooLong
		}
		switch {
		case err == nil:
			return trimEOL(buf), nil
		case errors.Is(err, bufio.ErrBufferFull):
			continue
		case errors.Is(err, io.EOF):
			return trimEOL(buf), io.EOF
		default:
			return nil, err
		}
	}
}

// contentLen returns an upper bound of the line content length seen so far.
// A trailing CR is not counted only when the line is complete, since an
// incomplete line's trailing CR may be followed by more content; in that
// case the CR is still tolerated by allowing one extra byte.
func contentLen(buf []byte, complete bool) int {
	if complete {
		return len(trimEOL(buf))
	}
	n := len(buf)
	if n > 0 && buf[n-1] == '\r' {
		n--
	}
	return n
}

func trimEOL(b []byte) []byte {
	b = bytes.TrimSuffix(b, []byte("\n"))
	return bytes.TrimSuffix(b, []byte("\r"))
}
