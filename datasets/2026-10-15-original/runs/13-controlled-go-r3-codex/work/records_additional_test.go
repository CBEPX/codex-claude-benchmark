package records

import (
	"errors"
	"io"
	"reflect"
	"strings"
	"testing"
)

func TestReadUniqueValidInput(t *testing.T) {
	longID := strings.Repeat("x", 70*1024)
	longLine := `{"id":"` + longID + `"}`
	tests := []struct {
		name  string
		input string
		limit int
		want  []Record
	}{
		{"empty", "", 1, []Record{}},
		{"blank lines", "\n\r\n\n", 1, []Record{}},
		{"CRLF at limit", "{\"id\":\"a\"}\r\n", 10, []Record{{ID: "a"}}},
		{"EOF at limit", `{"id":"a"}`, 10, []Record{{ID: "a"}}},
		{"large line", longLine + "\n", len(longLine), []Record{{ID: longID}}},
		{"byte length", `{"id":"я"}`, len(`{"id":"я"}`), []Record{{ID: "я"}}},
		{"largest limit", `{"id":"a"}`, int(^uint(0) >> 1), []Record{{ID: "a"}}},
		{
			"exact IDs and first occurrence",
			"{\"id\":\" a \",\"value\":1}\n{\"id\":\"a\",\"value\":2}\n{\"id\":\" a \",\"value\":3}\n{\"id\":\"b\",\"value\":4}",
			100,
			[]Record{{ID: " a ", Value: 1}, {ID: "a", Value: 2}, {ID: "b", Value: 4}},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := ReadUnique(strings.NewReader(tt.input), tt.limit)
			if err != nil || !reflect.DeepEqual(got, tt.want) {
				t.Fatalf("got %v records, error %v; want %v records", len(got), err, len(tt.want))
			}
		})
	}
}

func TestReadUniqueRejectsInvalidInput(t *testing.T) {
	tests := []struct {
		name  string
		input string
		limit int
	}{
		{"zero limit on empty stream", "", 0},
		{"negative limit on empty stream", "", -1},
		{"line too long", `{"id":"ab"}`, 10},
		{"CRLF line too long", "{\"id\":\"ab\"}\r\n", 10},
		{"byte limit", `{"id":"я"}`, len(`{"id":"я"}`) - 1},
		{"blank line too long", "   \n", 2},
		{"invalid JSON", "{", 100},
		{"trailing JSON", `{"id":"a"} {"id":"b"}`, 100},
		{"missing ID", `{}`, 100},
		{"empty ID", `{"id":""}`, 100},
		{"whitespace ID", `{"id":" \t\n\u2003"}`, 100},
		{"wrong ID type", `{"id":123}`, 100},
		{"null record", `null`, 100},
		{"duplicate invalid syntax", "{\"id\":\"a\"}\n{\"id\":\"a\",}", 100},
		{"duplicate invalid value", "{\"id\":\"a\"}\n{\"id\":\"a\",\"value\":\"bad\"}", 100},
		{"no partial result", "{\"id\":\"a\"}\n{}", 100},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := ReadUnique(strings.NewReader(tt.input), tt.limit)
			if err == nil || got != nil {
				t.Fatalf("got %v, %v; want nil result and error", got, err)
			}
		})
	}
}

type failingReader struct {
	data string
	err  error
}

func (r *failingReader) Read(p []byte) (int, error) {
	n := copy(p, r.data)
	r.data = r.data[n:]
	if len(r.data) > 0 {
		return n, nil
	}
	return n, r.err
}

func TestReadUniquePreservesReadError(t *testing.T) {
	sentinel := errors.New("reader failed")
	for _, data := range []string{"", `{"id":"a"}`, "{\"id\":\"a\"}\n", "{\"id\":\"a\"}\n{"} {
		t.Run(data, func(t *testing.T) {
			got, err := ReadUnique(&failingReader{data: data, err: sentinel}, 100)
			if got != nil || !errors.Is(err, sentinel) {
				t.Fatalf("got %v, %v; want nil result and reader error", got, err)
			}
		})
	}
	got, err := ReadUnique(&failingReader{data: `{"id":"a"}`, err: io.EOF}, 100)
	if err != nil || len(got) != 1 || got[0].ID != "a" {
		t.Fatalf("data returned with EOF was lost: %v, %v", got, err)
	}
}
