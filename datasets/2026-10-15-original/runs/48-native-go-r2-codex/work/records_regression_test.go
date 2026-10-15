package records

import (
	"errors"
	"io"
	"reflect"
	"strings"
	"testing"
)

func TestReadUniqueValidation(t *testing.T) {
	const valid = `{"id":"a","value":1}`
	long := `{"id":"` + strings.Repeat("x", 70*1024) + `","value":2}`
	for _, tc := range []struct {
		name  string
		input string
		limit int
		want  []Record
		bad   bool
	}{
		{name: "empty", limit: 1, want: []Record{}},
		{name: "zero limit", limit: 0, bad: true},
		{name: "negative limit", limit: -1, bad: true},
		{name: "blank lines", input: "\n\r\n \t\n", limit: 2, want: []Record{}},
		{name: "exact limit CRLF", input: valid + "\r\n", limit: len(valid), want: []Record{{ID: "a", Value: 1}}},
		{name: "final line", input: valid, limit: len(valid), want: []Record{{ID: "a", Value: 1}}},
		{name: "long line", input: long + "\n", limit: len(long), want: []Record{{ID: strings.Repeat("x", 70*1024), Value: 2}}},
		{name: "too long", input: valid, limit: len(valid) - 1, bad: true},
		{name: "blank too long", input: "   \n", limit: 2, bad: true},
		{name: "byte length", input: `{"id":"я"}`, limit: len(`{"id":"я"}`) - 1, bad: true},
		{name: "invalid JSON", input: valid + "\n{", limit: 100, bad: true},
		{name: "missing ID", input: valid + "\n{}", limit: 100, bad: true},
		{name: "blank ID", input: `{"id":" \t"}`, limit: 100, bad: true},
		{name: "null record", input: "null", limit: 100, bad: true},
		{name: "invalid duplicate", input: valid + "\n" + `{"id":"a","value":"bad"}`, limit: 100, bad: true},
		{name: "multiple JSON values", input: valid + valid, limit: 100, bad: true},
		{name: "exact IDs and order", input: valid + "\n" + `{"id":" a ","value":2}` + "\n" + `{"id":"a","value":3}` + "\n" + `{"id":"b","value":4}`, limit: 100, want: []Record{{ID: "a", Value: 1}, {ID: " a ", Value: 2}, {ID: "b", Value: 4}}},
	} {
		t.Run(tc.name, func(t *testing.T) {
			got, err := ReadUnique(strings.NewReader(tc.input), tc.limit)
			if tc.bad {
				if err == nil || got != nil {
					t.Fatalf("got %v, %v; want nil and error", got, err)
				}
			} else if err != nil || !reflect.DeepEqual(got, tc.want) {
				t.Fatalf("got %v, %v; want %v", got, err, tc.want)
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
	if len(r.data) == 0 {
		return n, r.err
	}
	return n, nil
}

func TestReadUniqueReaderError(t *testing.T) {
	sentinel := errors.New("read failed")
	for _, input := range []string{"", `{"id":"a"}`, "{\"id\":\"a\"}\n"} {
		got, err := ReadUnique(&failingReader{data: input, err: sentinel}, 100)
		if got != nil || !errors.Is(err, sentinel) {
			t.Fatalf("got %v, %v; want nil and reader error", got, err)
		}
	}
	got, err := ReadUnique(&failingReader{data: `{"id":"a"}`, err: io.EOF}, 100)
	if err != nil || len(got) != 1 || got[0].ID != "a" {
		t.Fatalf("data with EOF: got %v, %v", got, err)
	}
}
