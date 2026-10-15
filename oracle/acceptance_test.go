package records
import ("strings"; "testing"; "errors"; "io"; "reflect"; "fmt")
type brokenReader struct{}
func (brokenReader) Read(p []byte)(int,error){return 0,errors.New("broken-reader")}
type countingReader struct{reads int}
func (r *countingReader) Read(p []byte)(int,error){r.reads++;return 0,io.EOF}
func TestAcceptance(t *testing.T){
 cases:=[]struct{name,input string;limit int;want []Record;bad bool}{
 {"empty","",100,[]Record{},false},
 {"blank","\n  \n\t\n",100,[]Record{},false},
 {"order","{\"id\":\"z\",\"value\":1}\n{\"id\":\"a\",\"value\":2}\n{\"id\":\"z\",\"value\":9}",100,[]Record{{"z",1},{"a",2}},false},
 {"invalid","{\"id\":\"a\"}\nno",100,nil,true},
 {"missing-id","{\"value\":2}",100,nil,true},
 {"blank-id","{\"id\":\"  \"}",100,nil,true},
 {"zero-limit","",0,nil,true},
 {"negative-limit-empty","",-1,nil,true},
 {"zero-limit-data",`{"id":"a"}`,0,nil,true},
 {"exact-limit",`{"id":"a"}`,len(`{"id":"a"}`),[]Record{{"a",0}},false},
 {"valid-over-limit",`{"id":"a"}`,len(`{"id":"a"}`)-1,nil,true},
 {"utf8-byte-limit",`{"id":"é"}`,len(`{"id":"é"}`)-1,nil,true},
 {"untrimmed-id",`{"id":" a "}`+"\n"+`{"id":"a"}`,100,[]Record{{" a ",0},{"a",0}},false},
 {"invalid-duplicate",`{"id":"a"}`+"\n"+`{"id":"a","value":"bad"}`,100,nil,true},
 {"oversize-blank",strings.Repeat(" ",101),100,nil,true},
 {"maximum-limit-empty","",int(^uint(0)>>1),[]Record{},false},
 {"too-long",strings.Repeat("x",101),100,nil,true},
 {"exact-crlf",`{"id":"a"}`+"\r\n",len(`{"id":"a"}`),[]Record{{"a",0}},false},
 {"bare-cr-counts",`{"id":"a"}`+"\r",len(`{"id":"a"}`),nil,true},
 {"crlf","{\"id\":\"a\",\"value\":1}\r\n",100,[]Record{{"a",1}},false},
 }
 for _,c:=range cases{t.Run(c.name,func(t *testing.T){got,e:=ReadUnique(strings.NewReader(c.input),c.limit);if (e!=nil)!=c.bad{t.Fatalf("error=%v",e)};if c.bad{if got!=nil{t.Fatal("partial output")};return};if len(got)!=len(c.want)||len(got)>0&&!reflect.DeepEqual(got,c.want){t.Fatalf("got=%v want=%v",got,c.want)}})}
 for _,limit:=range []int{0,-1}{t.Run(fmt.Sprintf("no-read-%d",limit),func(t *testing.T){r:=&countingReader{};got,e:=ReadUnique(r,limit);if e==nil||got!=nil||r.reads!=0{t.Fatalf("got=%v err=%v reads=%d",got,e,r.reads)}})}
 _,e:=ReadUnique(brokenReader{},100);if e==nil||!strings.Contains(e.Error(),"broken-reader"){t.Fatalf("reader error lost: %v",e)}
 long:=fmt.Sprintf("{\"id\":\"%s\",\"value\":7}",strings.Repeat("a",70000));got,e:=ReadUnique(strings.NewReader(long),len(long));if e!=nil||len(got)!=1{t.Fatalf("long valid record: %v",e)}
 got,e=ReadUnique(io.MultiReader(strings.NewReader("{\"id\":\"a\"}\n"),brokenReader{}),100);if e==nil||got!=nil{t.Fatalf("partial reader failure: %v %v",got,e)}
}
