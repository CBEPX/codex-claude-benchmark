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

var (
	ErrInvalidLimit = errors.New("records: negative maxBytes")
	ErrLineTooLong  = errors.New("records: line exceeds maxBytes")
	ErrEmptyID      = errors.New("records: empty id")
)

// ReadUnique reads NDJSON records from r and returns the first record for
// each distinct ID in order of appearance. Empty lines are skipped. If
// maxBytes > 0, each line (excluding CR/LF) must be at most maxBytes long.
// On any error it returns nil and the error.
func ReadUnique(r io.Reader, maxBytes int) ([]Record, error) {
	if maxBytes < 0 {
		return nil, ErrInvalidLimit
	}
	br := bufio.NewReader(r)
	out := []Record{}
	seen := map[string]struct{}{}
	var line []byte
	for lineNo := 1; ; lineNo++ {
		var readErr error
		line, readErr = readLine(br, line[:0], maxBytes)
		if readErr != nil && readErr != io.EOF {
			if errors.Is(readErr, ErrLineTooLong) {
				return nil, fmt.Errorf("line %d: %w", lineNo, readErr)
			}
			return nil, fmt.Errorf("records: read line %d: %w", lineNo, readErr)
		}
		if len(line) > 0 {
			var v Record
			if err := json.Unmarshal(line, &v); err != nil {
				return nil, fmt.Errorf("records: line %d: %w", lineNo, err)
			}
			if strings.TrimSpace(v.ID) == "" {
				return nil, fmt.Errorf("line %d: %w", lineNo, ErrEmptyID)
			}
			if _, ok := seen[v.ID]; !ok {
				seen[v.ID] = struct{}{}
				out = append(out, v)
			}
		}
		if readErr == io.EOF {
			return out, nil
		}
	}
}

// readLine appends the next line's content (without the trailing LF or
// CRLF) to buf. It returns io.EOF when the stream ended at this line.
func readLine(br *bufio.Reader, buf []byte, maxBytes int) ([]byte, error) {
	for {
		chunk, err := br.ReadSlice('\n')
		buf = append(buf, chunk...)
		// One extra byte is tolerated for a possible trailing CR.
		if maxBytes > 0 && len(bytes.TrimSuffix(buf, []byte("\n"))) > maxBytes+1 {
			return buf, ErrLineTooLong
		}
		if err == bufio.ErrBufferFull {
			continue
		}
		if err != nil && err != io.EOF {
			return buf, err
		}
		buf = bytes.TrimSuffix(buf, []byte("\n"))
		buf = bytes.TrimSuffix(buf, []byte("\r"))
		if maxBytes > 0 && len(buf) > maxBytes {
			return buf, ErrLineTooLong
		}
		return buf, err
	}
}
