package records

import (
	"errors"
	"io"
	"reflect"
	"strings"
	"testing"
)

func TestReadUniqueLines(t *testing.T) {
	longID := strings.Repeat("x", 70*1024)
	tests := []struct {
		name  string
		input string
		limit int
		want  []Record
	}{
		{"empty", "", 1, []Record{}},
		{"blank lines", "\n\r\n \t\n", 2, []Record{}},
		{"CRLF exact limit", "{\"id\":\"я\"}\r\n", len(`{"id":"я"}`), []Record{{ID: "я"}}},
		{"final CR", "{\"id\":\"a\"}\r", len(`{"id":"a"}`), []Record{{ID: "a"}}},
		{"large line", `{"id":"` + longID + `"}`, len(longID) + 9, []Record{{ID: longID}}},
		{"exact IDs and order", "{\"id\":\" a \",\"value\":1}\n{\"id\":\"a\",\"value\":2}\n{\"id\":\" a \",\"value\":3}", 100, []Record{{ID: " a ", Value: 1}, {ID: "a", Value: 2}}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := ReadUnique(strings.NewReader(tt.input), tt.limit)
			if err != nil || !reflect.DeepEqual(got, tt.want) {
				t.Fatalf("got %v, %v; want %v", got, err, tt.want)
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
		{"invalid JSON after valid record", "{\"id\":\"a\"}\n{", 100},
		{"duplicate with invalid value", "{\"id\":\"a\"}\n{\"id\":\"a\",\"value\":\"bad\"}", 100},
		{"missing ID", "{}", 100},
		{"blank ID", `{"id":" \t\n"}`, 100},
		{"null record", "null", 100},
		{"trailing JSON", `{"id":"a"} {}`, 100},
		{"byte limit", `{"id":"я"}`, len(`{"id":"я"}`) - 1},
		{"oversized blank line", "   \n", 2},
		{"oversized duplicate", "{\"id\":\"a\"}\n{\"id\":\"a\",\"value\":1}", len(`{"id":"a"}`)},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := ReadUnique(strings.NewReader(tt.input), tt.limit)
			if err == nil || got != nil {
				t.Fatalf("got %v, %v; want nil and an error", got, err)
			}
		})
	}
}

type failingRecordReader struct {
	data string
	err  error
}

func (r *failingRecordReader) Read(p []byte) (int, error) {
	n := copy(p, r.data)
	r.data = r.data[n:]
	return n, r.err
}

func TestReadUniquePreservesReaderError(t *testing.T) {
	sentinel := errors.New("read failed")
	for _, data := range []string{"", `{"id":"a"}`, "{\"id\":\"a\"}\n", "{"} {
		for _, afterRecord := range []bool{false, true} {
			var reader io.Reader = &failingRecordReader{data: data, err: sentinel}
			if afterRecord {
				reader = io.MultiReader(strings.NewReader("{\"id\":\"first\"}\n"), reader)
			}
			got, err := ReadUnique(reader, 100)
			if got != nil || !errors.Is(err, sentinel) {
				t.Fatalf("data %q, afterRecord %v: got %v, %v; want nil and reader error", data, afterRecord, got, err)
			}
		}
	}
}
