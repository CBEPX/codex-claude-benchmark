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

// ReadUnique reads NDJSON records from r and returns the first record for
// each distinct ID in order of appearance. Empty lines are skipped. If
// maxBytes > 0, each line (excluding the CR/LF terminator) must be at most
// maxBytes long. On any error it returns nil and the error.
func ReadUnique(r io.Reader, maxBytes int) ([]Record, error) {
	if maxBytes < 0 {
		return nil, fmt.Errorf("records: invalid maxBytes %d", maxBytes)
	}
	if r == nil {
		return nil, errors.New("records: nil reader")
	}
	br := bufio.NewReader(r)
	out := []Record{}
	seen := make(map[string]struct{})
	for lineNo := 1; ; lineNo++ {
		line, err := readLine(br, maxBytes)
		if err != nil && err != io.EOF {
			return nil, fmt.Errorf("records: line %d: %w", lineNo, err)
		}
		if line == nil && err == io.EOF {
			return out, nil
		}
		if len(bytes.TrimSpace(line)) > 0 {
			v, perr := parseRecord(line)
			if perr != nil {
				return nil, fmt.Errorf("records: line %d: %w", lineNo, perr)
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

var errLineTooLong = errors.New("line exceeds maxBytes")

// readLine returns the next line without its trailing LF or CRLF. It returns
// (nil, io.EOF) when no more data is available and (line, io.EOF) for a final
// line without a terminator. Any other read error is returned as is.
func readLine(br *bufio.Reader, maxBytes int) ([]byte, error) {
	var buf []byte
	got := false
	for {
		chunk, err := br.ReadSlice('\n')
		if len(chunk) > 0 {
			got = true
			buf = append(buf, chunk...)
			// Content may be up to maxBytes plus an optional CR and LF.
			if maxBytes > 0 && len(buf) > maxBytes+2 {
				return nil, errLineTooLong
			}
		}
		if err == bufio.ErrBufferFull {
			continue
		}
		if err != nil && err != io.EOF {
			return nil, err
		}
		if !got && err == io.EOF {
			return nil, io.EOF
		}
		terminated := err == nil
		if terminated {
			buf = buf[:len(buf)-1]
		}
		buf = bytes.TrimSuffix(buf, []byte{'\r'})
		if maxBytes > 0 && len(buf) > maxBytes {
			return nil, errLineTooLong
		}
		if buf == nil {
			buf = []byte{}
		}
		if terminated {
			return buf, nil
		}
		return buf, io.EOF
	}
}

func parseRecord(line []byte) (Record, error) {
	var v Record
	dec := json.NewDecoder(bytes.NewReader(line))
	if err := dec.Decode(&v); err != nil {
		return Record{}, fmt.Errorf("invalid JSON: %w", err)
	}
	if _, err := dec.Token(); err != io.EOF {
		return Record{}, errors.New("invalid JSON: trailing data after record")
	}
	if strings.TrimSpace(v.ID) == "" {
		return Record{}, errors.New("empty id")
	}
	return v, nil
}
