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
	for lineNumber := 1; ; lineNumber++ {
		line, readErr := reader.ReadString('\n')
		if readErr != nil && readErr != io.EOF {
			return nil, fmt.Errorf("read line %d: %w", lineNumber, readErr)
		}
		line = strings.TrimSuffix(line, "\n")
		line = strings.TrimSuffix(line, "\r")
		if len(line) > maxBytes {
			return nil, fmt.Errorf("line %d exceeds maxBytes (%d)", lineNumber, maxBytes)
		}
		if strings.TrimSpace(line) != "" {
			var record Record
			if err := json.Unmarshal([]byte(line), &record); err != nil {
				return nil, fmt.Errorf("line %d: %w", lineNumber, err)
			}
			if strings.TrimSpace(record.ID) == "" {
				return nil, fmt.Errorf("line %d: id must not be blank", lineNumber)
			}
			if _, exists := seen[record.ID]; !exists {
				seen[record.ID] = struct{}{}
				out = append(out, record)
			}
		}
		if readErr == io.EOF {
			return out, nil
		}
	}
}
