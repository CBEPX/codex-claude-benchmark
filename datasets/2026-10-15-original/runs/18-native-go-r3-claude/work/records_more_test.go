package records

import (
	"errors"
	"strings"
	"testing"
)

type errReader struct {
	data []byte
	err  error
}

func (e *errReader) Read(p []byte) (int, error) {
	n := copy(p, e.data)
	e.data = e.data[n:]
	if len(e.data) == 0 {
		return n, e.err
	}
	return n, nil
}

func TestValidInputs(t *testing.T) {
	long := `{"id":"big","value":1,"pad":"` + strings.Repeat("x", 70*1024) + `"}`
	for _, tc := range []struct {
		name string
		in   string
		max  int
		ids  []string
	}{
		{"empty stream", "", 0, nil},
		{"blank lines", "\n\r\n{\"id\":\"a\"}\n\n", 0, []string{"a"}},
		{"long line", long + "\n", 0, []string{"big"}},
		{"exact limit", `{"id":"a"}`, len(`{"id":"a"}`), []string{"a"}},
		{"crlf not counted", "{\"id\":\"a\"}\r\n{\"id\":\"b\"}\r", len(`{"id":"a"}`), []string{"a", "b"}},
		{"order and exact ids", "{\"id\":\"b\"}\n{\"id\":\" b\"}\n{\"id\":\"a\"}\n{\"id\":\"b\",\"value\":9}", 0, []string{"b", " b", "a"}},
	} {
		r, err := ReadUnique(strings.NewReader(tc.in), tc.max)
		if err != nil || r == nil || len(r) != len(tc.ids) {
			t.Fatalf("%s: %v %v", tc.name, r, err)
		}
		for i, id := range tc.ids {
			if r[i].ID != id {
				t.Fatalf("%s: got %v", tc.name, r)
			}
		}
	}
}

func TestInvalidInputs(t *testing.T) {
	for _, tc := range []struct {
		name string
		in   string
		max  int
	}{
		{"negative limit on empty stream", "", -1},
		{"over limit", `{"id":"ab"}`, len(`{"id":"a"}`)},
		{"blank over limit", strings.Repeat(" ", 11) + "\n", 10},
		{"whitespace line", "{\"id\":\"a\"}\n  \n", 0},
		{"bad json after valid", "{\"id\":\"a\"}\n{bad\n", 0},
		{"bad duplicate", "{\"id\":\"a\"}\n{\"id\":\"a\",\"value\":\"x\"}\n", 0},
		{"blank id", `{"id":"  "}`, 0},
		{"missing id", `{"value":1}`, 0},
		{"null", "null", 0},
		{"trailing data", `{"id":"a"} {}`, 0},
	} {
		if r, err := ReadUnique(strings.NewReader(tc.in), tc.max); err == nil || r != nil {
			t.Fatalf("%s: %v %v", tc.name, r, err)
		}
	}
}

func TestReadErrorKept(t *testing.T) {
	sentinel := errors.New("boom")
	for _, in := range []string{"{\"id\":\"a\"}\n", "{\"id\":\"a\"}\n{\"id\":\"b"} {
		r, err := ReadUnique(&errReader{data: []byte(in), err: sentinel}, 0)
		if !errors.Is(err, sentinel) || r != nil {
			t.Fatalf("%q: %v %v", in, r, err)
		}
	}
}
