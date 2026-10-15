package records

import (
	"errors"
	"io"
	"strings"
	"testing"
)

// oneShotErr returns data together with err once, then io.EOF.
type oneShotErr struct {
	data string
	err  error
	done bool
}

func (o *oneShotErr) Read(p []byte) (int, error) {
	if o.done {
		return 0, io.EOF
	}
	o.done = true
	return copy(p, o.data), o.err
}

func TestReadUniqueCases(t *testing.T) {
	big := `{"id":"big","value":7,"pad":"` + strings.Repeat("x", 100<<10) + `"}`
	tests := []struct {
		name    string
		in      string
		max     int
		wantIDs []string
		wantErr bool
	}{
		{"empty stream zero limit", "", 0, nil, true},
		{"empty stream negative limit", "", -1, nil, true},
		{"empty stream", "", 10, []string{}, false},
		{"blank lines skipped", "\n\r\n{\"id\":\"a\"}\r\n\n{\"id\":\"b\"}\r", 100, []string{"a", "b"}, false},
		{"order and first wins", `{"id":"b"}` + "\n" + `{"id":"a"}` + "\n" + `{"id":"b","value":9}`, 100, []string{"b", "a"}, false},
		{"exact id not normalized", `{"id":"a"}` + "\n" + `{"id":" a"}`, 100, []string{"a", " a"}, false},
		{"line over 64KiB", big + "\n", 1 << 20, []string{"big"}, false},
		{"limit exact", `{"id":"a"}` + "\r\n", 10, []string{"a"}, false},
		{"limit exceeded", `{"id":"a"}` + "\r\n", 9, nil, true},
		{"limit exceeded long line", big, 1000, nil, true},
		{"limit exceeded by blank-ish line", "            \n", 3, nil, true},
		{"whitespace-only line", "  \n", 100, nil, true},
		{"bad json", `{"id":"a"}` + "\n" + `{bad`, 100, nil, true},
		{"bad duplicate", `{"id":"a"}` + "\n" + `{"id":"a","value":"x"}`, 100, nil, true},
		{"missing id", `{"value":1}`, 100, nil, true},
		{"blank id", `{"id":"  "}`, 100, nil, true},
		{"null", `null`, 100, nil, true},
		{"trailing data", `{"id":"a"} {"id":"b"}`, 100, nil, true},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got, err := ReadUnique(strings.NewReader(tc.in), tc.max)
			if tc.wantErr {
				if err == nil || got != nil {
					t.Fatalf("want nil, error; got %v, %v", got, err)
				}
				return
			}
			if err != nil || got == nil || len(got) != len(tc.wantIDs) {
				t.Fatalf("got %v, %v; want ids %v", got, err, tc.wantIDs)
			}
			for i, id := range tc.wantIDs {
				if got[i].ID != id {
					t.Fatalf("got %v; want ids %v", got, tc.wantIDs)
				}
			}
		})
	}
}

func TestReadUniqueKeepsReadError(t *testing.T) {
	boom := errors.New("boom")
	got, err := ReadUnique(&oneShotErr{data: `{"id":"a"}` + "\n" + `{"id":"b"}`, err: boom}, 100)
	if got != nil || !errors.Is(err, boom) {
		t.Fatalf("got %v, %v; want nil, boom", got, err)
	}
}

func TestReadUniqueNilReader(t *testing.T) {
	if got, err := ReadUnique(nil, 100); got != nil || err == nil {
		t.Fatalf("got %v, %v", got, err)
	}
}
