package records
import ("strings"; "testing")
func TestBasic(t *testing.T) { r,e:=ReadUnique(strings.NewReader("{\"id\":\"a\",\"value\":1}\n"),100); if e!=nil || len(r)!=1 || r[0].ID!="a" { t.Fatalf("%v %v",r,e) } }
func TestDeduplicate(t *testing.T) { r,e:=ReadUnique(strings.NewReader("{\"id\":\"a\",\"value\":1}\n{\"id\":\"a\",\"value\":2}"),100); if e!=nil || len(r)!=1 || r[0].Value!=1 { t.Fatalf("%v %v",r,e) } }
