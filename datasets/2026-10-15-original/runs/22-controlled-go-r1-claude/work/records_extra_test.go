package records

import (
	"errors"
	"io"
	"math"
	"strings"
	"testing"
	"testing/iotest"
)

func TestInvalidMaxBytesOnEmptyStream(t *testing.T) {
	for _, m := range []int{0, -1} {
		r, err := ReadUnique(strings.NewReader(""), m)
		if err == nil || r != nil {
			t.Fatalf("maxBytes=%d: got %v %v", m, r, err)
		}
	}
}

func TestEmptyStream(t *testing.T) {
	r, err := ReadUnique(strings.NewReader(""), 10)
	if err != nil || r == nil || len(r) != 0 {
		t.Fatalf("%v %v", r, err)
	}
}

func TestBlankLinesAndCRLF(t *testing.T) {
	in := "\n\r\n{\"id\":\"a\",\"value\":1}\r\n  \n{\"id\":\"b\",\"value\":2}\r"
	r, err := ReadUnique(strings.NewReader(in), 100)
	if err != nil || len(r) != 2 || r[0].ID != "a" || r[1].ID != "b" {
		t.Fatalf("%v %v", r, err)
	}
}

func TestLongLine(t *testing.T) {
	id := strings.Repeat("x", 200000)
	line := `{"id":"` + id + `","value":7}`
	in := line + "\n" + line + "\n{\"id\":\"y\"}"
	r, err := ReadUnique(strings.NewReader(in), len(line))
	if err != nil || len(r) != 2 || r[0].ID != id || r[0].Value != 7 || r[1].ID != "y" {
		t.Fatalf("len=%d err=%v", len(r), err)
	}
	if _, err := ReadUnique(strings.NewReader(in), math.MaxInt); err != nil {
		t.Fatal(err)
	}
}

func TestLineLimit(t *testing.T) {
	line := `{"id":"a"}`
	cases := []struct {
		in  string
		max int
		ok  bool
	}{
		{line, len(line), true},
		{line + "\r\n", len(line), true},
		{line + "\r", len(line), true},
		{line, len(line) - 1, false},
		{line + "\n", len(line) - 1, false},
		{"     \n" + line, 3, false},
		{strings.Repeat(" ", 100000) + line + "\r\n", len(line) + 99999, false},
		{strings.Repeat(" ", 100000) + line + "\r\n", len(line) + 100000, true},
	}
	for i, c := range cases {
		r, err := ReadUnique(strings.NewReader(c.in), c.max)
		if c.ok != (err == nil) || (err != nil && r != nil) {
			t.Fatalf("case %d: %v %v", i, r, err)
		}
	}
}

func TestInvalidRecords(t *testing.T) {
	for _, in := range []string{
		"{\"id\":\"a\"}\n{\"id\":\"a\"",
		"{\"id\":\"a\"}\n{\"id\":\"a\"} x",
		"{\"id\":\"a\"}\n{\"id\":\"  \"}",
		"{\"id\":\"a\"}\n{\"value\":1}",
		"{\"id\":\"a\"}\nnull",
		"{\"id\":\"a\"}\n[]",
		"{\"id\":\"a\"}\n{\"id\":1}",
		"{\"id\":\"a\"}\n{\"id\":\"a\",\"value\":\"x\"}",
	} {
		r, err := ReadUnique(strings.NewReader(in), 100)
		if err == nil || r != nil {
			t.Fatalf("%q: %v %v", in, r, err)
		}
	}
}

func TestExactIDs(t *testing.T) {
	in := "{\"id\":\"a\"}\n{\"id\":\" a\"}\n{\"id\":\"A\"}\n{\"id\":\"a\",\"value\":5}"
	r, err := ReadUnique(strings.NewReader(in), 100)
	if err != nil || len(r) != 3 || r[0].ID != "a" || r[1].ID != " a" || r[2].ID != "A" || r[0].Value != 0 {
		t.Fatalf("%v %v", r, err)
	}
}

func TestReadError(t *testing.T) {
	boom := errors.New("boom")
	readers := []io.Reader{
		io.MultiReader(strings.NewReader("{\"id\":\"a\"}\n{\"id\":\"b\"}"), iotest.ErrReader(boom)),
		iotest.DataErrReader(io.MultiReader(strings.NewReader("{\"id\":\"a\"}\n"), iotest.ErrReader(boom))),
		iotest.OneByteReader(io.MultiReader(strings.NewReader("{\"id\":\"a\"}\n"), iotest.ErrReader(boom))),
	}
	for i, rd := range readers {
		r, err := ReadUnique(rd, 100)
		if !errors.Is(err, boom) || r != nil {
			t.Fatalf("reader %d: %v %v", i, r, err)
		}
	}
}
