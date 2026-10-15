package records

import (
	"errors"
	"io"
	"reflect"
	"strings"
	"testing"
)

func TestReadUniqueEdges(t *testing.T) {
	const valid = `{"id":"a","value":1}`
	longID := strings.Repeat("x", 70*1024)
	longLine := `{"id":"` + longID + `","value":2}`
	tests := []struct {
		name  string
		input string
		limit int
		want  []Record
		bad   bool
	}{
		{name: "empty", limit: 1, want: []Record{}},
		{name: "zero limit on empty input", limit: 0, bad: true},
		{name: "negative limit on empty input", limit: -1, bad: true},
		{name: "blank lines", input: "\n\r\n \t\n" + valid + "\n", limit: 100, want: []Record{{ID: "a", Value: 1}}},
		{name: "exact limit LF", input: valid + "\n", limit: len(valid), want: []Record{{ID: "a", Value: 1}}},
		{name: "exact limit CRLF", input: valid + "\r\n", limit: len(valid), want: []Record{{ID: "a", Value: 1}}},
		{name: "exact limit EOF", input: valid, limit: len(valid), want: []Record{{ID: "a", Value: 1}}},
		{name: "over limit", input: valid, limit: len(valid) - 1, bad: true},
		{name: "blank over limit", input: "   \n", limit: 2, bad: true},
		{name: "large line", input: longLine + "\r\n", limit: len(longLine), want: []Record{{ID: longID, Value: 2}}},
		{name: "large line over limit", input: longLine, limit: len(longLine) - 1, bad: true},
		{name: "invalid JSON after valid", input: valid + "\n{", limit: 100, bad: true},
		{name: "invalid duplicate", input: valid + "\n" + `{"id":"a","value":"bad"}`, limit: 100, bad: true},
		{name: "missing ID", input: `{"value":1}`, limit: 100, bad: true},
		{name: "blank ID", input: `{"id":" \t\n"}`, limit: 100, bad: true},
		{name: "null record", input: `null`, limit: 100, bad: true},
		{name: "multiple JSON values", input: valid + valid, limit: 100, bad: true},
		{name: "byte limit", input: `{"id":"я"}`, limit: len(`{"id":"я"}`) - 1, bad: true},
		{
			name: "exact IDs and first appearance",
			input: valid + "\n" + `{"id":" a ","value":2}` + "\n" +
				`{"id":"a","value":3}` + "\n" + `{"id":"b","value":4}`,
			limit: 100,
			want:  []Record{{ID: "a", Value: 1}, {ID: " a ", Value: 2}, {ID: "b", Value: 4}},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := ReadUnique(strings.NewReader(tt.input), tt.limit)
			if tt.bad {
				if err == nil || got != nil {
					t.Fatalf("expected nil result and error, got %v, %v", got, err)
				}
				return
			}
			if err != nil || !reflect.DeepEqual(got, tt.want) {
				t.Fatalf("got %v, %v; want %v", got, err, tt.want)
			}
		})
	}
}

type recordsFailingReader struct {
	data string
	err  error
}

func (r *recordsFailingReader) Read(p []byte) (int, error) {
	n := copy(p, r.data)
	r.data = r.data[n:]
	if len(r.data) == 0 {
		return n, r.err
	}
	return n, nil
}

func TestReadUniqueReaderErrors(t *testing.T) {
	failure := errors.New("reader failed")
	for _, data := range []string{"", `{"id":"a"}`, "{\"id\":\"a\"}\n", "{\"id\":\"a\"}\n{"} {
		for _, reader := range []io.Reader{
			&recordsFailingReader{data: data, err: failure},
			io.MultiReader(strings.NewReader(data), &recordsFailingReader{err: failure}),
		} {
			got, err := ReadUnique(reader, 100)
			if got != nil || !errors.Is(err, failure) {
				t.Fatalf("input %q: expected nil and reader failure, got %v, %v", data, got, err)
			}
		}
	}
}
