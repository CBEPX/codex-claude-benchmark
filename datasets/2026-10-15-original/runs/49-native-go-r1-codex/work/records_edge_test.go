package records

import (
	"errors"
	"io"
	"reflect"
	"strings"
	"testing"
)

func TestReadUniqueEdges(t *testing.T) {
	line := `{"id":"a","value":1}`
	largeID := strings.Repeat("x", 70*1024)
	largeLine := `{"id":"` + largeID + `"}`
	for _, tc := range []struct {
		name, input string
		limit       int
		want        []Record
		wantErr     bool
	}{
		{"empty", "", 1, []Record{}, false},
		{"zero limit", "", 0, nil, true},
		{"negative limit", "", -1, nil, true},
		{"blank lines", "\n\r\n \t\n", 2, []Record{}, false},
		{"boundary CRLF", line + "\r\n", len(line), []Record{{ID: "a", Value: 1}}, false},
		{"boundary EOF", line, len(line), []Record{{ID: "a", Value: 1}}, false},
		{"too long", line, len(line) - 1, nil, true},
		{"blank too long", "   \n", 2, nil, true},
		{"byte limit", `{"id":"я"}`, len(`{"id":"я"}`) - 1, nil, true},
		{"large", largeLine, len(largeLine), []Record{{ID: largeID}}, false},
		{"exact IDs", line + "\n" + `{"id":" a "}` + "\n" + `{"id":"a","value":2}`, 100, []Record{{ID: "a", Value: 1}, {ID: " a "}}, false},
		{"malformed after valid", line + "\n{", 100, nil, true},
		{"malformed duplicate", line + "\n" + `{"id":"a","value":"bad"}`, 100, nil, true},
		{"missing ID", `{}`, 100, nil, true},
		{"blank ID", `{"id":" \t\n"}`, 100, nil, true},
		{"null", `null`, 100, nil, true},
		{"trailing JSON", line + `{}`, 100, nil, true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			got, err := ReadUnique(strings.NewReader(tc.input), tc.limit)
			if (err != nil) != tc.wantErr || !reflect.DeepEqual(got, tc.want) {
				t.Fatalf("got %v records, err=%v; want %v records, error=%v", len(got), err, len(tc.want), tc.wantErr)
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
	readErr := errors.New("read failed")
	for _, data := range []string{"", `{"id":"a"}`, "{\"id\":\"a\"}\n", "{\"id\":\"a\"}\n{\"id\":\"b\"}"} {
		got, err := ReadUnique(&failingReader{data: data, err: readErr}, 100)
		if got != nil || !errors.Is(err, readErr) {
			t.Fatalf("input %q: got %v, err=%v; want nil and reader error", data, got, err)
		}
	}
	got, err := ReadUnique(&failingReader{data: `{"id":"a"}`, err: io.EOF}, 100)
	if err != nil || len(got) != 1 || got[0].ID != "a" {
		t.Fatalf("data with EOF: got %v, err=%v", got, err)
	}
}
