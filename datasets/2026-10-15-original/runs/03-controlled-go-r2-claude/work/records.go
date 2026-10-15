package records

import (
	"bufio"
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

// ReadUnique reads NDJSON records from r, skipping empty lines and keeping
// only the first record for each exact ID in order of appearance.
// maxBytes > 0 limits the length of each line without its CR/LF terminator;
// maxBytes == 0 means no limit. On any error it returns nil and the error.
func ReadUnique(r io.Reader, maxBytes int) ([]Record, error) {
	if maxBytes < 0 {
		return nil, ErrInvalidLimit
	}
	br := bufio.NewReader(r)
	out := []Record{}
	seen := map[string]struct{}{}
	for n := 1; ; n++ {
		line, eof, err := readLine(br, maxBytes)
		if err != nil {
			return nil, fmt.Errorf("line %d: %w", n, err)
		}
		if len(line) > 0 {
			var v Record
			if err := json.Unmarshal(line, &v); err != nil {
				return nil, fmt.Errorf("line %d: %w", n, err)
			}
			if strings.TrimSpace(v.ID) == "" {
				return nil, fmt.Errorf("line %d: %w", n, ErrEmptyID)
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

// readLine returns the next line without its trailing "\n" or "\r\n".
// eof reports that the stream ended after this line. Lines longer than
// maxBytes (when positive) are rejected without buffering the remainder.
func readLine(br *bufio.Reader, maxBytes int) (line []byte, eof bool, err error) {
	for {
		chunk, rerr := br.ReadSlice('\n')
		if rerr != nil && rerr != bufio.ErrBufferFull && rerr != io.EOF {
			return nil, false, rerr
		}
		line = append(line, chunk...)
		if maxBytes > 0 && len(line) > maxBytes+2 {
			return nil, false, ErrLineTooLong
		}
		if rerr == bufio.ErrBufferFull {
			continue
		}
		eof = rerr == io.EOF
		break
	}
	if !eof {
		line = line[:len(line)-1]
	}
	if len(line) > 0 && line[len(line)-1] == '\r' {
		line = line[:len(line)-1]
	}
	if maxBytes > 0 && len(line) > maxBytes {
		return nil, false, ErrLineTooLong
	}
	return line, eof, nil
}
