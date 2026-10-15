package records

import (
	"errors"
	"io"
	"reflect"
	"strings"
	"testing"
)

func TestReadUniqueEdges(t *testing.T) {
	const first = `{"id":"a","value":1}`
	tests := []struct {
		name  string
		input string
		limit int
		want  []Record
		fail  bool
	}{
		{name: "empty", limit: 1, want: []Record{}},
		{name: "zero limit on empty input", fail: true},
		{name: "negative limit on empty input", limit: -1, fail: true},
		{name: "blank lines", input: "\n\r\n \t\n", limit: 2, want: []Record{}},
		{name: "CRLF at limit", input: first + "\r\n", limit: len(first), want: []Record{{ID: "a", Value: 1}}},
		{name: "EOF at limit", input: first, limit: len(first), want: []Record{{ID: "a", Value: 1}}},
		{name: "too long", input: first + "\n", limit: len(first) - 1, fail: true},
		{name: "blank too long", input: "   \n", limit: 2, fail: true},
		{name: "byte limit", input: `{"id":"я"}`, limit: len(`{"id":"я"}`) - 1, fail: true},
		{name: "invalid JSON after valid", input: first + "\n{", limit: 100, fail: true},
		{name: "invalid duplicate", input: first + "\n" + `{"id":"a","value":"bad"}`, limit: 100, fail: true},
		{name: "missing ID", input: first + "\n{}", limit: 100, fail: true},
		{name: "null record", input: "null", limit: 100, fail: true},
		{name: "whitespace ID", input: `{"id":" \t\u2003"}`, limit: 100, fail: true},
		{name: "multiple JSON values", input: first + first, limit: 100, fail: true},
		{
			name: "exact IDs and first occurrence order",
			input: first + "\n" + `{"id":" a ","value":2}` + "\n" +
				`{"id":"b","value":3}` + "\n" + `{"id":"a","value":4}`,
			limit: 100,
			want:  []Record{{ID: "a", Value: 1}, {ID: " a ", Value: 2}, {ID: "b", Value: 3}},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := ReadUnique(strings.NewReader(tt.input), tt.limit)
			if tt.fail {
				if err == nil || got != nil {
					t.Fatalf("got %v, %v; want nil result and error", got, err)
				}
				return
			}
			if err != nil || !reflect.DeepEqual(got, tt.want) {
				t.Fatalf("got %v, %v; want %v", got, err, tt.want)
			}
		})
	}
}

func TestReadUniqueLargeLine(t *testing.T) {
	id := strings.Repeat("x", 70*1024)
	line := `{"id":"` + id + `","value":7}`
	got, err := ReadUnique(strings.NewReader(line+"\r\n"), len(line))
	if err != nil || len(got) != 1 || got[0] != (Record{ID: id, Value: 7}) {
		t.Fatalf("large line: count %d, error %v", len(got), err)
	}
}

type recordErrorReader struct {
	data string
	err  error
}

func (r *recordErrorReader) Read(p []byte) (int, error) {
	n := copy(p, r.data)
	r.data = r.data[n:]
	if len(r.data) == 0 {
		return n, r.err
	}
	return n, nil
}

func TestReadUniqueReaderError(t *testing.T) {
	sentinel := errors.New("reader failed")
	for _, suffix := range []string{"", "\n", "\r\n"} {
		t.Run("suffix="+suffix, func(t *testing.T) {
			for _, together := range []bool{false, true} {
				data := `{"id":"a","value":1}` + suffix
				var reader io.Reader = &recordErrorReader{data: data, err: sentinel}
				if !together {
					reader = io.MultiReader(strings.NewReader(data), &recordErrorReader{err: sentinel})
				}
				got, err := ReadUnique(reader, 100)
				if got != nil || !errors.Is(err, sentinel) {
					t.Fatalf("together=%v: got %v, %v; want nil and reader error", together, got, err)
				}
			}
		})
	}
}
