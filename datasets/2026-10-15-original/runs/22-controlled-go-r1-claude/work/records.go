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
// distinct ID in order of appearance. Blank lines are skipped. maxBytes must be
// positive and limits the length of each line excluding the CR/LF terminator.
// On any error no records are returned.
func ReadUnique(r io.Reader, maxBytes int) ([]Record, error) {
	if maxBytes <= 0 {
		return nil, fmt.Errorf("records: invalid maxBytes %d: must be positive", maxBytes)
	}
	br := bufio.NewReader(r)
	out := []Record{}
	seen := make(map[string]struct{})
	for lineNo := 1; ; lineNo++ {
		line, eof, err := readLine(br, maxBytes)
		if err != nil {
			return nil, fmt.Errorf("records: line %d: %w", lineNo, err)
		}
		if eof && line == nil {
			break
		}
		if len(bytes.TrimSpace(line)) > 0 {
			var v Record
			if err := json.Unmarshal(line, &v); err != nil {
				return nil, fmt.Errorf("records: line %d: invalid JSON: %w", lineNo, err)
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
			break
		}
	}
	return out, nil
}

// readLine reads one line without its trailing LF or CRLF. It stops reading as
// soon as the content is known to exceed maxBytes. At end of input it returns
// eof=true; line is nil if no bytes remained.
func readLine(br *bufio.Reader, maxBytes int) (line []byte, eof bool, err error) {
	for {
		chunk, err := br.ReadSlice('\n')
		line = append(line, chunk...)
		switch {
		case err == nil:
			line = line[:len(line)-1]
			line = bytes.TrimSuffix(line, []byte{'\r'})
			if len(line) > maxBytes {
				return nil, false, fmt.Errorf("line exceeds %d bytes", maxBytes)
			}
			if line == nil {
				line = []byte{}
			}
			return line, false, nil
		case errors.Is(err, bufio.ErrBufferFull):
			// A trailing CR may still be stripped, so allow one extra byte.
			if len(line)-1 > maxBytes {
				return nil, false, fmt.Errorf("line exceeds %d bytes", maxBytes)
			}
		case err == io.EOF:
			if len(line) == 0 {
				return nil, true, nil
			}
			line = bytes.TrimSuffix(line, []byte{'\r'})
			if len(line) > maxBytes {
				return nil, false, fmt.Errorf("line exceeds %d bytes", maxBytes)
			}
			return line, true, nil
		default:
			return nil, false, fmt.Errorf("read: %w", err)
		}
	}
}
