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

// ReadUnique reads NDJSON records from r and returns the first record for each
// exact ID in order of appearance. Empty lines are skipped. If maxBytes > 0, it
// limits the length of each line's content (excluding the CR/LF terminator).
// On any error, it returns nil and the error.
func ReadUnique(r io.Reader, maxBytes int) ([]Record, error) {
	if maxBytes < 0 {
		return nil, fmt.Errorf("records: invalid maxBytes %d", maxBytes)
	}
	if r == nil {
		return nil, errors.New("records: nil reader")
	}
	br := bufio.NewReader(r)
	out := []Record{}
	seen := map[string]struct{}{}
	for lineNo := 1; ; lineNo++ {
		line, eof, err := readLine(br, maxBytes)
		if err != nil {
			return nil, fmt.Errorf("records: line %d: %w", lineNo, err)
		}
		if len(line) > 0 {
			var v Record
			if err := json.Unmarshal(line, &v); err != nil {
				return nil, fmt.Errorf("records: line %d: invalid JSON: %w", lineNo, err)
			}
			if strings.TrimSpace(v.ID) == "" {
				return nil, fmt.Errorf("records: line %d: empty id", lineNo)
			}
			if _, ok := seen[v.ID]; !ok {
				seen[v.ID] = struct{}{}
				out = append(out, v)
			}
		}
		if eof {
			return out, nil
		}
	}
}

// readLine reads one line without its trailing LF or CRLF. eof reports that
// the input ended with this line. Lines longer than maxBytes (when > 0) are
// rejected without buffering them entirely.
func readLine(br *bufio.Reader, maxBytes int) (line []byte, eof bool, err error) {
	for {
		chunk, rerr := br.ReadSlice('\n')
		line = append(line, chunk...)
		// Allow one extra byte for a possible CR before LF.
		if maxBytes > 0 && len(line) > maxBytes+2 {
			return nil, false, fmt.Errorf("line exceeds %d bytes", maxBytes)
		}
		switch {
		case rerr == nil:
			line = line[:len(line)-1]
		case errors.Is(rerr, bufio.ErrBufferFull):
			continue
		case rerr == io.EOF:
			eof = true
		default:
			return nil, false, fmt.Errorf("read: %w", rerr)
		}
		break
	}
	line = bytes.TrimSuffix(line, []byte{'\r'})
	if maxBytes > 0 && len(line) > maxBytes {
		return nil, false, fmt.Errorf("line exceeds %d bytes", maxBytes)
	}
	return line, eof, nil
}
