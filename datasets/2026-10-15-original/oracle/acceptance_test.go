package records
import ("strings"; "testing"; "errors"; "io"; "reflect"; "fmt")
type brokenReader struct{}
func (brokenReader) Read(p []byte)(int,error){return 0,errors.New("broken-reader")}
func TestAcceptance(t *testing.T){
 cases:=[]struct{name,input string;limit int;want []Record;bad bool}{
 {"empty","",100,[]Record{},false},
 {"blank","\n  \n\t\n",100,[]Record{},false},
 {"order","{\"id\":\"z\",\"value\":1}\n{\"id\":\"a\",\"value\":2}\n{\"id\":\"z\",\"value\":9}",100,[]Record{{"z",1},{"a",2}},false},
 {"invalid","{\"id\":\"a\"}\nno",100,nil,true},
 {"missing-id","{\"value\":2}",100,nil,true},
 {"blank-id","{\"id\":\"  \"}",100,nil,true},
 {"zero-limit","",0,nil,true},
 {"too-long",strings.Repeat("x",101),100,nil,true},
 {"crlf","{\"id\":\"a\",\"value\":1}\r\n",100,[]Record{{"a",1}},false},
 }
 for _,c:=range cases{t.Run(c.name,func(t *testing.T){got,e:=ReadUnique(strings.NewReader(c.input),c.limit);if (e!=nil)!=c.bad{t.Fatalf("error=%v",e)};if c.bad{if got!=nil{t.Fatal("partial output")};return};if len(got)!=len(c.want)||len(got)>0&&!reflect.DeepEqual(got,c.want){t.Fatalf("got=%v want=%v",got,c.want)}})}
 _,e:=ReadUnique(brokenReader{},100);if e==nil||!strings.Contains(e.Error(),"broken-reader"){t.Fatalf("reader error lost: %v",e)}
 long:=fmt.Sprintf("{\"id\":\"%s\",\"value\":7}",strings.Repeat("a",70000));got,e:=ReadUnique(strings.NewReader(long),len(long));if e!=nil||len(got)!=1{t.Fatalf("long valid record: %v",e)}
 got,e=ReadUnique(io.MultiReader(strings.NewReader("{\"id\":\"a\"}\n"),brokenReader{}),100);if e==nil||got!=nil{t.Fatalf("partial reader failure: %v %v",got,e)}
}
