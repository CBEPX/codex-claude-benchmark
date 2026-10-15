package records

import (
	"errors"
	"io"
	"strings"
	"testing"
	"testing/iotest"
)

func TestEmptyAndBlankLines(t *testing.T) {
	r, e := ReadUnique(strings.NewReader("\n\r\n{\"id\":\"a\",\"value\":1}\r\n\n{\"id\":\"b\",\"value\":2}"), 100)
	if e != nil || len(r) != 2 || r[0].ID != "a" || r[1].ID != "b" {
		t.Fatalf("%v %v", r, e)
	}
	r, e = ReadUnique(strings.NewReader(""), 0)
	if e != nil || r == nil || len(r) != 0 {
		t.Fatalf("%v %v", r, e)
	}
}

func TestInvalidLimitOnEmptyStream(t *testing.T) {
	if r, e := ReadUnique(strings.NewReader(""), -1); e == nil || r != nil {
		t.Fatalf("%v %v", r, e)
	}
}

func TestLimitExcludesCRLF(t *testing.T) {
	line := `{"id":"a","value":1}`
	if r, e := ReadUnique(strings.NewReader(line+"\r\n"), len(line)); e != nil || len(r) != 1 {
		t.Fatalf("%v %v", r, e)
	}
	if r, e := ReadUnique(strings.NewReader(line+"\r\n"), len(line)-1); e == nil || r != nil {
		t.Fatalf("%v %v", r, e)
	}
	if r, e := ReadUnique(strings.NewReader(line), len(line)-1); e == nil || r != nil {
		t.Fatalf("%v %v", r, e)
	}
}

func TestLongLine(t *testing.T) {
	id := strings.Repeat("x", 200<<10)
	in := `{"id":"` + id + `","value":3}` + "\n"
	r, e := ReadUnique(strings.NewReader(in), 0)
	if e != nil || len(r) != 1 || r[0].ID != id {
		t.Fatalf("len=%d %v", len(r), e)
	}
	if r, e := ReadUnique(strings.NewReader(in), 1000); e == nil || r != nil {
		t.Fatalf("%v", e)
	}
}

func TestIDValidationAndExactMatch(t *testing.T) {
	for _, in := range []string{`{"id":"","value":1}`, `{"id":"  ","value":1}`, `{"value":1}`, `null`} {
		if r, e := ReadUnique(strings.NewReader(in), 0); e == nil || r != nil {
			t.Fatalf("%q: %v %v", in, r, e)
		}
	}
	r, e := ReadUnique(strings.NewReader("{\"id\":\" a\",\"value\":1}\n{\"id\":\"a\",\"value\":2}\n"), 0)
	if e != nil || len(r) != 2 || r[0].ID != " a" {
		t.Fatalf("%v %v", r, e)
	}
}

func TestInvalidJSONNoPartial(t *testing.T) {
	for _, in := range []string{
		"{\"id\":\"a\",\"value\":1}\n{bad\n",
		"{\"id\":\"a\",\"value\":1}\n{\"id\":\"a\",\"value\":\"x\"}\n",
		"{\"id\":\"a\",\"value\":1} {\"id\":\"b\",\"value\":2}\n",
		"{\"id\":\"a\",\"value\":1}\n{\"id\":\"a\"\n",
	} {
		if r, e := ReadUnique(strings.NewReader(in), 0); e == nil || r != nil {
			t.Fatalf("%q: %v %v", in, r, e)
		}
	}
}

func TestReaderError(t *testing.T) {
	boom := errors.New("boom")
	in := io.MultiReader(strings.NewReader("{\"id\":\"a\",\"value\":1}\n"), iotest.ErrReader(boom))
	r, e := ReadUnique(in, 0)
	if !errors.Is(e, boom) || r != nil {
		t.Fatalf("%v %v", r, e)
	}
	r, e = ReadUnique(iotest.DataErrReader(strings.NewReader("{\"id\":\"a\",\"value\":1}")), 0)
	if e != nil || len(r) != 1 {
		t.Fatalf("%v %v", r, e)
	}
}
