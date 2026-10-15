package records

import (
	"errors"
	"io"
	"reflect"
	"strings"
	"testing"
)

func TestReadUniqueLineBoundaries(t *testing.T) {
	line := `{"id":"я","value":1}`
	for _, ending := range []string{"", "\n", "\r\n", "\r"} {
		t.Run("ending="+ending, func(t *testing.T) {
			got, err := ReadUnique(strings.NewReader("\n\r\n \t\n"+line+ending), len(line))
			if err != nil || !reflect.DeepEqual(got, []Record{{ID: "я", Value: 1}}) {
				t.Fatalf("got %v, %v", got, err)
			}
			got, err = ReadUnique(strings.NewReader(line+ending), len(line)-1)
			if err == nil || got != nil {
				t.Fatalf("expected length error and nil result, got %v, %v", got, err)
			}
		})
	}
}

func TestReadUniqueLongLine(t *testing.T) {
	id := strings.Repeat("x", 100000)
	line := `{"id":"` + id + `","value":7}`
	got, err := ReadUnique(strings.NewReader(line+"\r\n"), len(line))
	if err != nil || !reflect.DeepEqual(got, []Record{{ID: id, Value: 7}}) {
		t.Fatalf("long record: count=%d, error=%v", len(got), err)
	}
}

func TestReadUniquePreservesExactIDsAndOrder(t *testing.T) {
	input := `{"id":" b ","value":1}` + "\n" +
		`{"id":"a","value":2}` + "\n" +
		`{"id":" b ","value":3}` + "\n" +
		`{"id":"b","value":4}`
	want := []Record{{ID: " b ", Value: 1}, {ID: "a", Value: 2}, {ID: "b", Value: 4}}
	got, err := ReadUnique(strings.NewReader(input), 100)
	if err != nil || !reflect.DeepEqual(got, want) {
		t.Fatalf("got %v, %v; want %v", got, err, want)
	}
}

func TestReadUniqueRejectsInvalidInput(t *testing.T) {
	valid := `{"id":"a","value":1}` + "\n"
	for _, input := range []string{
		`{`,
		`{"id":"a","value":"bad"}`,
		`{"id":"a"} {"id":"b"}`,
		`{"value":2}`,
		`{"id":""}`,
		`{"id":" \t\n"}`,
		`null`,
		strings.Repeat(" ", 101),
		`{"id":"` + strings.Repeat("a", 101) + `"}`,
	} {
		t.Run(input, func(t *testing.T) {
			got, err := ReadUnique(strings.NewReader(valid+input), 100)
			if err == nil || got != nil {
				t.Fatalf("expected error and nil result, got %v, %v", got, err)
			}
		})
	}
}

func TestReadUniqueEmptyInputAndInvalidLimits(t *testing.T) {
	for _, limit := range []int{-1, 0} {
		got, err := ReadUnique(strings.NewReader(""), limit)
		if err == nil || got != nil {
			t.Fatalf("limit %d: got %v, %v", limit, got, err)
		}
	}
	got, err := ReadUnique(strings.NewReader(""), 1)
	if err != nil || len(got) != 0 {
		t.Fatalf("empty input: got %v, %v", got, err)
	}
}

type failingRecordReader struct {
	data string
	err  error
}

func (r *failingRecordReader) Read(p []byte) (int, error) {
	n := copy(p, r.data)
	r.data = r.data[n:]
	if len(r.data) == 0 {
		return n, r.err
	}
	return n, nil
}

func TestReadUniquePreservesReaderError(t *testing.T) {
	wantErr := errors.New("read failure")
	for _, data := range []string{"", `{"id":"a"}`, "{\"id\":\"a\"}\n", "{\"id\":\"a\"}\n{"} {
		got, err := ReadUnique(&failingRecordReader{data: data, err: wantErr}, 100)
		if got != nil || !errors.Is(err, wantErr) {
			t.Fatalf("input %q: got %v, %v; want nil and reader error", data, got, err)
		}
	}
	got, err := ReadUnique(&failingRecordReader{data: `{"id":"a"}`, err: io.EOF}, 100)
	if err != nil || !reflect.DeepEqual(got, []Record{{ID: "a"}}) {
		t.Fatalf("data with EOF: got %v, %v", got, err)
	}
}
