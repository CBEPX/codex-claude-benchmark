package records

import (
	"bufio"
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
		line, err := reader.ReadString('\n')
		if err != nil && err != io.EOF {
			return nil, err
		}
		line = strings.TrimSuffix(line, "\n")
		line = strings.TrimSuffix(line, "\r")
		if len(line) > maxBytes {
			return nil, fmt.Errorf("line exceeds maxBytes (%d)", maxBytes)
		}
		if strings.TrimSpace(line) != "" {
			var record Record
			if err := json.Unmarshal([]byte(line), &record); err != nil {
				return nil, err
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
