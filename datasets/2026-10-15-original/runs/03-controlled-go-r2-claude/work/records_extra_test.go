package records

import (
	"errors"
	"io"
	"strings"
	"testing"
)

type failReader struct {
	data string
	err  error
}

func (f *failReader) Read(p []byte) (int, error) {
	if f.data == "" {
		return 0, f.err
	}
	n := copy(p, f.data)
	f.data = f.data[n:]
	return n, nil
}

func TestLargeLine(t *testing.T) {
	id := strings.Repeat("x", 100<<10)
	in := `{"id":"` + id + `","value":7}` + "\n"
	r, e := ReadUnique(strings.NewReader(in), 0)
	if e != nil || len(r) != 1 || r[0].ID != id || r[0].Value != 7 {
		t.Fatalf("%d %v", len(r), e)
	}
	r, e = ReadUnique(strings.NewReader(in), len(in)-1)
	if e != nil || len(r) != 1 {
		t.Fatalf("%d %v", len(r), e)
	}
}

func TestLimit(t *testing.T) {
	line := `{"id":"a","value":1}`
	r, e := ReadUnique(strings.NewReader(line+"\r\n\r\n"+line), len(line))
	if e != nil || len(r) != 1 {
		t.Fatalf("%v %v", r, e)
	}
	r, e = ReadUnique(strings.NewReader(line+"\n"), len(line)-1)
	if e == nil || r != nil || !errors.Is(e, ErrLineTooLong) {
		t.Fatalf("%v %v", r, e)
	}
	r, e = ReadUnique(strings.NewReader(strings.Repeat(" ", 1<<20)), 10)
	if e == nil || r != nil {
		t.Fatalf("%v %v", r, e)
	}
}

func TestNegativeLimitEmptyStream(t *testing.T) {
	r, e := ReadUnique(strings.NewReader(""), -1)
	if e == nil || r != nil {
		t.Fatalf("%v %v", r, e)
	}
}

func TestEmptyStream(t *testing.T) {
	r, e := ReadUnique(strings.NewReader("\n\r\n"), 5)
	if e != nil || r == nil || len(r) != 0 {
		t.Fatalf("%v %v", r, e)
	}
}

func TestOrderAndExactID(t *testing.T) {
	in := `{"id":"b","value":1}` + "\n" + `{"id":" b","value":2}` + "\n" + `{"id":"a","value":3}` + "\n" + `{"id":"b","value":4}`
	r, e := ReadUnique(strings.NewReader(in), 0)
	if e != nil || len(r) != 3 || r[0].ID != "b" || r[1].ID != " b" || r[2].ID != "a" || r[0].Value != 1 {
		t.Fatalf("%v %v", r, e)
	}
}

func TestInvalid(t *testing.T) {
	for _, in := range []string{
		`{"id":"a","value":1}` + "\n" + `{"id":"a","value":"x"}`,
		`{"id":"a","value":1}` + "\n" + `{"id":"a"`,
		`{"id":"a","value":1} x`,
		`null`,
		`{"value":1}`,
		`{"id":"  ","value":1}`,
		`{"id":1}`,
		"   ",
	} {
		r, e := ReadUnique(strings.NewReader(in), 0)
		if e == nil || r != nil {
			t.Fatalf("%q: %v %v", in, r, e)
		}
	}
}

func TestReadError(t *testing.T) {
	boom := errors.New("boom")
	r, e := ReadUnique(&failReader{data: `{"id":"a","value":1}` + "\n" + `{"id":"b"`, err: boom}, 0)
	if !errors.Is(e, boom) || r != nil {
		t.Fatalf("%v %v", r, e)
	}
	r, e = ReadUnique(&failReader{err: io.ErrUnexpectedEOF}, 0)
	if !errors.Is(e, io.ErrUnexpectedEOF) || r != nil {
		t.Fatalf("%v %v", r, e)
	}
}
