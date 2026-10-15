package records

import (
	"bufio"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math"
	"strings"
)

type Record struct {
	ID    string `json:"id"`
	Value int    `json:"value"`
}

// ReadUnique reads NDJSON records, skipping empty lines and keeping the first
// record for each exact ID. maxBytes > 0 limits line content (without CR/LF);
// 0 means no limit. Any error returns nil records.
func ReadUnique(r io.Reader, maxBytes int) ([]Record, error) {
	if maxBytes < 0 {
		return nil, fmt.Errorf("records: negative maxBytes %d", maxBytes)
	}
	s := bufio.NewScanner(r)
	bufMax := math.MaxInt
	if maxBytes > 0 && maxBytes <= math.MaxInt-2 {
		bufMax = maxBytes + 2 // room for "\r\n"
	}
	s.Buffer(nil, bufMax)

	// A truncated last line is an artifact of a read error; report the read error.
	fail := func(err error) ([]Record, error) {
		if rerr := s.Err(); rerr != nil {
			return nil, rerr
		}
		return nil, err
	}

	out := []Record{}
	seen := map[string]bool{}
	for n := 1; s.Scan(); n++ {
		line := s.Bytes()
		if maxBytes > 0 && len(line) > maxBytes {
			return fail(fmt.Errorf("records: line %d: %d bytes exceeds limit %d", n, len(line), maxBytes))
		}
		if len(line) == 0 {
			continue
		}
		var v Record
		if err := json.Unmarshal(line, &v); err != nil {
			return fail(fmt.Errorf("records: line %d: %w", n, err))
		}
		if strings.TrimSpace(v.ID) == "" {
			return fail(fmt.Errorf("records: line %d: empty id", n))
		}
		if seen[v.ID] {
			continue
		}
		seen[v.ID] = true
		out = append(out, v)
	}
	if err := s.Err(); err != nil {
		if errors.Is(err, bufio.ErrTooLong) {
			return nil, fmt.Errorf("records: line exceeds limit %d: %w", maxBytes, err)
		}
		return nil, err
	}
	return out, nil
}
