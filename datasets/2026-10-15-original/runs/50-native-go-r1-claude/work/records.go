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

// ReadUnique reads NDJSON records, skipping empty lines, and returns the first
// record for each exact ID in order of appearance. maxBytes must be positive
// and limits each line's length excluding CR/LF. On any error it returns nil.
func ReadUnique(r io.Reader, maxBytes int) ([]Record, error) {
	if maxBytes <= 0 {
		return nil, fmt.Errorf("records: maxBytes must be positive, got %d", maxBytes)
	}
	if r == nil {
		return nil, errors.New("records: nil reader")
	}
	br := bufio.NewReader(r)
	out := []Record{}
	seen := map[string]struct{}{}
	var line []byte
	for n := 1; ; n++ {
		line = line[:0]
		var err error
		for {
			var frag []byte
			frag, err = br.ReadSlice('\n')
			line = append(line, frag...)
			if err != bufio.ErrBufferFull {
				break
			}
			// A trailing CR may still belong to the line ending.
			if len(line)-1 > maxBytes {
				return nil, fmt.Errorf("records: line %d exceeds %d bytes", n, maxBytes)
			}
		}
		if err != nil && err != io.EOF {
			return nil, err
		}
		content := bytes.TrimSuffix(bytes.TrimSuffix(line, []byte("\n")), []byte("\r"))
		if len(content) > maxBytes {
			return nil, fmt.Errorf("records: line %d exceeds %d bytes", n, maxBytes)
		}
		if len(content) > 0 {
			var v Record
			if err := json.Unmarshal(content, &v); err != nil {
				return nil, fmt.Errorf("records: line %d: %w", n, err)
			}
			if strings.TrimSpace(v.ID) == "" {
				return nil, fmt.Errorf("records: line %d: empty id", n)
			}
			if _, ok := seen[v.ID]; !ok {
				seen[v.ID] = struct{}{}
				out = append(out, v)
			}
		}
		if err == io.EOF {
			return out, nil
		}
	}
}
