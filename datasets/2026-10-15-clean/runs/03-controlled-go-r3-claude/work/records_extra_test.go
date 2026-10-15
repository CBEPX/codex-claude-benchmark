package records

import (
	"errors"
	"io"
	"strings"
	"testing"
	"testing/iotest"
)

func TestEmptyAndBlank(t *testing.T) {
	for _, in := range []string{"", "\n", "\r\n\n  \n"} {
		r, e := ReadUnique(strings.NewReader(in), 10)
		if e != nil || r == nil || len(r) != 0 {
			t.Fatalf("%q: %v %v", in, r, e)
		}
	}
}

func TestNegativeLimitOnEmpty(t *testing.T) {
	if r, e := ReadUnique(strings.NewReader(""), -1); e == nil || r != nil {
		t.Fatalf("%v %v", r, e)
	}
}

func TestLimitExcludesCRLF(t *testing.T) {
	line := `{"id":"a","value":1}`
	r, e := ReadUnique(strings.NewReader(line+"\r\n"+line+"\r"), len(line))
	if e != nil || len(r) != 1 {
		t.Fatalf("%v %v", r, e)
	}
	r, e = ReadUnique(strings.NewReader(line+"\n"), len(line)-1)
	if !errors.Is(e, ErrLineTooLong) || r != nil {
		t.Fatalf("%v %v", r, e)
	}
	// Whitespace-only line still counts against the limit.
	r, e = ReadUnique(strings.NewReader(strings.Repeat(" ", 5)+"\n"), 4)
	if !errors.Is(e, ErrLineTooLong) || r != nil {
		t.Fatalf("%v %v", r, e)
	}
}

func TestLongLine(t *testing.T) {
	id := strings.Repeat("x", 200<<10)
	in := `{"id":"` + id + `","value":7}` + "\n"
	r, e := ReadUnique(strings.NewReader(in), 0)
	if e != nil || len(r) != 1 || r[0].ID != id || r[0].Value != 7 {
		t.Fatalf("len=%d %v", len(r), e)
	}
	r, e = ReadUnique(strings.NewReader(in), len(in)-1)
	if e != nil || len(r) != 1 {
		t.Fatalf("len=%d %v", len(r), e)
	}
	r, e = ReadUnique(strings.NewReader(in), 100)
	if !errors.Is(e, ErrLineTooLong) || r != nil {
		t.Fatalf("%v", e)
	}
}

func TestInvalid(t *testing.T) {
	cases := []string{
		`{"id":"a"}` + "\n" + `not json`,
		`{"id":"a"}` + "\n" + `{"id":"a"`, // invalid duplicate
		`{"id":"   "}`,
		`{"value":1}`,
		`null`,
		`{"id":"a"} {"id":"b"}`,
		`{"id":"a","value":"x"}`,
	}
	for _, in := range cases {
		if r, e := ReadUnique(strings.NewReader(in), 0); e == nil || r != nil {
			t.Fatalf("%q: %v %v", in, r, e)
		}
	}
}

func TestOrderAndExactID(t *testing.T) {
	in := `{"id":"b","value":1}` + "\n" + `{"id":" b","value":2}` + "\n\n" +
		`{"id":"a","value":3}` + "\n" + `{"id":"b","value":4}`
	r, e := ReadUnique(strings.NewReader(in), 0)
	if e != nil || len(r) != 3 || r[0].ID != "b" || r[0].Value != 1 || r[1].ID != " b" || r[2].ID != "a" {
		t.Fatalf("%v %v", r, e)
	}
}

func TestReaderError(t *testing.T) {
	boom := errors.New("boom")
	src := io.MultiReader(strings.NewReader(`{"id":"a"}`+"\n"), iotest.ErrReader(boom))
	if r, e := ReadUnique(src, 0); !errors.Is(e, boom) || r != nil {
		t.Fatalf("%v %v", r, e)
	}
	// Error returned together with data.
	src = iotest.DataErrReader(io.MultiReader(strings.NewReader(`{"id":"a"}`), iotest.ErrReader(boom)))
	if r, e := ReadUnique(src, 0); !errors.Is(e, boom) || r != nil {
		t.Fatalf("%v %v", r, e)
	}
}
