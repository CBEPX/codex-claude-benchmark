package records

import (
	"errors"
	"io"
	"reflect"
	"strings"
	"testing"
)

func TestReadUniqueValidation(t *testing.T) {
	largeID := strings.Repeat("x", 70*1024)
	for _, tc := range []struct {
		name  string
		input string
		limit int
		want  []Record
		bad   bool
	}{
		{name: "empty", limit: 1, want: []Record{}},
		{name: "zero limit empty", limit: 0, bad: true},
		{name: "negative limit empty", limit: -1, bad: true},
		{name: "blank lines", input: "\n\r\n \t\n", limit: 2, want: []Record{}},
		{name: "crlf boundary", input: "{\"id\":\"a\"}\r\n", limit: 10, want: []Record{{ID: "a"}}},
		{name: "final line boundary", input: "{\"id\":\"a\"}", limit: 10, want: []Record{{ID: "a"}}},
		{name: "too long", input: "{\"id\":\"a\"}\n", limit: 9, bad: true},
		{name: "byte limit", input: "{\"id\":\"я\"}", limit: 10, bad: true},
		{name: "long blank", input: "   \n", limit: 2, bad: true},
		{name: "large record", input: "{\"id\":\"" + largeID + "\"}\n", limit: len(largeID) + 9, want: []Record{{ID: largeID}}},
		{name: "exact IDs and order", input: "{\"id\":\"b\",\"value\":1}\n{\"id\":\" a \"}\n{\"id\":\"a\"}\n{\"id\":\"b\",\"value\":2}", limit: 100, want: []Record{{ID: "b", Value: 1}, {ID: " a "}, {ID: "a"}}},
		{name: "malformed after valid", input: "{\"id\":\"a\"}\n{", limit: 100, bad: true},
		{name: "invalid duplicate", input: "{\"id\":\"a\"}\n{\"id\":\"a\",\"value\":\"bad\"}", limit: 100, bad: true},
		{name: "missing ID", input: "{}", limit: 100, bad: true},
		{name: "empty ID", input: "{\"id\":\"\"}", limit: 100, bad: true},
		{name: "blank ID", input: "{\"id\":\" \\t\\u2003\"}", limit: 100, bad: true},
		{name: "null", input: "null", limit: 100, bad: true},
		{name: "multiple JSON values", input: "{\"id\":\"a\"} {}", limit: 100, bad: true},
		{name: "length after valid", input: "{\"id\":\"a\"}\n{\"id\":\"long\"}", limit: 10, bad: true},
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
	io.Reader
	err error
}

func (r failingReader) Read(p []byte) (int, error) {
	n, _ := r.Reader.Read(p)
	return n, r.err
}

func TestReadUniqueReaderError(t *testing.T) {
	wantErr := errors.New("read failed")
	for _, input := range []string{"", "{\"id\":\"a\"}", "{\"id\":\"a\"}\n", "{\"id\":\"a\"}\n{"} {
		got, err := ReadUnique(failingReader{strings.NewReader(input), wantErr}, 100)
		if got != nil || !errors.Is(err, wantErr) {
			t.Fatalf("input %q: got %v, %v; want nil and reader error", input, got, err)
		}
	}
}
