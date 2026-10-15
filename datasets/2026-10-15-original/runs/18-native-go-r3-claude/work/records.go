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

var errLineTooLong = errors.New("line exceeds maxBytes")

// ReadUnique reads NDJSON records, skipping empty lines and keeping the first
// record of each exact ID in input order. maxBytes > 0 limits each line's
// length without its CR/LF terminator; 0 means no limit. Any error yields nil.
func ReadUnique(r io.Reader, maxBytes int) ([]Record, error) {
	if maxBytes < 0 {
		return nil, fmt.Errorf("records: negative maxBytes %d", maxBytes)
	}
	br := bufio.NewReader(r)
	out := []Record{}
	seen := map[string]bool{}
	for n := 1; ; n++ {
		line, err := readLine(br, maxBytes)
		if err == io.EOF {
			return out, nil
		}
		if errors.Is(err, errLineTooLong) {
			return nil, fmt.Errorf("records: line %d: %w", n, err)
		}
		if err != nil {
			return nil, fmt.Errorf("records: read line %d: %w", n, err)
		}
		if len(line) == 0 {
			continue
		}
		var v Record
		if err := json.Unmarshal(line, &v); err != nil {
			return nil, fmt.Errorf("records: line %d: %w", n, err)
		}
		if strings.TrimSpace(v.ID) == "" {
			return nil, fmt.Errorf("records: line %d: empty id", n)
		}
		if !seen[v.ID] {
			seen[v.ID] = true
			out = append(out, v)
		}
	}
}

// readLine returns the next line without its trailing LF or CRLF. It returns
// io.EOF only when no bytes remain, and stops buffering once maxBytes is exceeded.
func readLine(br *bufio.Reader, maxBytes int) ([]byte, error) {
	var line []byte
	for {
		chunk, err := br.ReadSlice('\n')
		line = append(line, chunk...)
		if maxBytes > 0 && len(line)-2 > maxBytes {
			return nil, errLineTooLong
		}
		if err == bufio.ErrBufferFull {
			continue
		}
		if err == io.EOF && len(line) > 0 {
			break
		}
		if err != nil {
			return nil, err
		}
		break
	}
	line = bytes.TrimSuffix(line, []byte("\n"))
	line = bytes.TrimSuffix(line, []byte("\r"))
	if maxBytes > 0 && len(line) > maxBytes {
		return nil, errLineTooLong
	}
	return line, nil
}
