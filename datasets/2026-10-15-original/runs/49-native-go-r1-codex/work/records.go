package records

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"strings"
)

type Record struct {
	ID    string `json:"id"`
	Value int    `json:"value"`
}

func ReadUnique(r io.Reader, maxBytes int) ([]Record, error) {
	if maxBytes <= 0 {
		return nil, fmt.Errorf("maxBytes must be positive")
	}
	reader := bufio.NewReader(r)
	out := []Record{}
	seen := make(map[string]struct{})
	for {
		line, err := reader.ReadBytes('\n')
		if err != nil && err != io.EOF {
			return nil, fmt.Errorf("read records: %w", err)
		}
		line = bytes.TrimSuffix(line, []byte{'\n'})
		line = bytes.TrimSuffix(line, []byte{'\r'})
		if len(line) > maxBytes {
			return nil, fmt.Errorf("record line exceeds %d bytes", maxBytes)
		}
		if len(bytes.TrimSpace(line)) > 0 {
			var record Record
			if jsonErr := json.Unmarshal(line, &record); jsonErr != nil {
				return nil, fmt.Errorf("decode record: %w", jsonErr)
			}
			if strings.TrimSpace(record.ID) == "" {
				return nil, fmt.Errorf("record ID must not be blank")
			}
			if _, exists := seen[record.ID]; !exists {
				seen[record.ID] = struct{}{}
				out = append(out, record)
			}
		}
		if err == io.EOF {
			return out, nil
		}
	}
}
