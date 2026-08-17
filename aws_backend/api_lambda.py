import json, os, uuid
from datetime import datetime, timezone
from decimal import Decimal
import boto3

TABLE_NAME=os.getenv("DYNAMODB_TABLE","DeadlineTasks"); ALLOWED_ORIGIN=os.getenv("ALLOWED_ORIGIN","*")
table=boto3.resource("dynamodb").Table(TABLE_NAME)
def convert(v):
    if isinstance(v,Decimal): return int(v) if v%1==0 else float(v)
    raise TypeError
def reply(code,body): return {"statusCode":code,"headers":{"Content-Type":"application/json","Access-Control-Allow-Origin":ALLOWED_ORIGIN,"Access-Control-Allow-Headers":"Content-Type,Authorization","Access-Control-Allow-Methods":"GET,POST,PUT,DELETE,OPTIONS"},"body":json.dumps(body,default=convert)}
def claims(e): return e.get("requestContext",{}).get("authorizer",{}).get("jwt",{}).get("claims",{})
def profile_id(uid): return f"USER#{uid}"
def scan_owned(uid):
    items=[]; args={"FilterExpression":"owner_id=:u AND item_type=:t","ExpressionAttributeValues":{":u":uid,":t":"task"}}
    while True:
        result=table.scan(**args); items.extend(result.get("Items",[]))
        if not result.get("LastEvaluatedKey"): return items
        args["ExclusiveStartKey"]=result["LastEvaluatedKey"]
def task_values(d):
    if any(not d.get(x) for x in ("title","module","task_type","deadline","difficulty")): raise ValueError("Please complete all required fields")
    return {"title":str(d["title"]).strip(),"module":str(d["module"]).strip().upper(),"task_type":str(d["task_type"]),"deadline":str(d["deadline"]),"description":str(d.get("description","")).strip(),"estimated_hours":Decimal(str(max(0,float(d.get("estimated_hours",1))))),"grade_weight":Decimal(str(max(0,min(100,float(d.get("grade_weight",0)))))),"difficulty":str(d["difficulty"]),"progress":Decimal(max(0,min(100,int(d.get("progress",0))))),"reminder_hours":Decimal(max(1,int(d.get("reminder_hours",24)))),"reminder_enabled":bool(d.get("reminder_enabled",True)),"work_mode":str(d.get("work_mode","Individual"))}

def lambda_handler(event,context):
    try:
        http=event.get("requestContext",{}).get("http",{}); method=http.get("method",event.get("httpMethod","GET")); path=event.get("rawPath",event.get("path","/"))
        if method=="OPTIONS": return reply(204,{})
        if method=="GET" and path=="/health": table.load(); return reply(200,{"status":"ok","table":TABLE_NAME})
        c=claims(event); uid=c.get("sub"); email=c.get("email","")
        if not uid: return reply(401,{"error":"Please sign in"})
        data=json.loads(event.get("body") or "{}")
        if path=="/me" and method=="GET":
            p=table.get_item(Key={"task_id":profile_id(uid)}).get("Item",{})
            return reply(200,{"profile":{"email":email,"notifications_enabled":p.get("notifications_enabled",True),"display_name":p.get("display_name",c.get("name",email.split("@")[0]))}})
        if path=="/me/preferences" and method=="PUT":
            table.update_item(Key={"task_id":profile_id(uid)},UpdateExpression="SET item_type=:t,owner_id=:u,email=:e,notifications_enabled=:n,display_name=:d,updated_at=:a",ExpressionAttributeValues={":t":"profile",":u":uid,":e":email,":n":bool(data.get("notifications_enabled",True)),":d":str(data.get("display_name","")).strip(),":a":datetime.now(timezone.utc).isoformat()}); return reply(200,{"message":"Preferences saved"})
        if path=="/tasks" and method=="GET": return reply(200,{"tasks":scan_owned(uid)})
        if path=="/tasks" and method=="POST":
            item=task_values(data); item.update({"task_id":str(uuid.uuid4()),"item_type":"task","owner_id":uid,"owner_email":email,"status":"Pending","created_at":datetime.now(timezone.utc).isoformat(),"reminder_sent":False}); table.put_item(Item=item,ConditionExpression="attribute_not_exists(task_id)"); return reply(201,{"task":item})
        parts=[x for x in path.split("/") if x]
        if len(parts)>=2 and parts[0]=="tasks":
            task_id=parts[1]; old=table.get_item(Key={"task_id":task_id}).get("Item")
            if not old or old.get("owner_id")!=uid: return reply(404,{"error":"Task not found"})
            if method=="DELETE": table.delete_item(Key={"task_id":task_id},ConditionExpression="owner_id=:u",ExpressionAttributeValues={":u":uid}); return reply(200,{"message":"Task deleted"})
            if method=="POST" and len(parts)==3 and parts[2]=="complete": table.update_item(Key={"task_id":task_id},UpdateExpression="SET #s=:s,progress=:p",ConditionExpression="owner_id=:u",ExpressionAttributeNames={"#s":"status"},ExpressionAttributeValues={":s":"Completed",":p":Decimal(100),":u":uid}); return reply(200,{"message":"Task completed"})
            if method=="PUT":
                v=task_values(data); v["reminder_sent"]=False; names={f"#k{i}":k for i,k in enumerate(v)}; vals={f":v{i}":x for i,x in enumerate(v.values())}; vals[":u"]=uid
                table.update_item(Key={"task_id":task_id},UpdateExpression="SET "+",".join(f"#k{i}=:v{i}" for i in range(len(v))),ConditionExpression="owner_id=:u",ExpressionAttributeNames=names,ExpressionAttributeValues=vals); return reply(200,{"message":"Task updated"})
        return reply(404,{"error":"Route not found"})
    except ValueError as e: return reply(400,{"error":str(e)})
    except Exception as e: print(repr(e)); return reply(500,{"error":"Server error. Check Lambda logs."})
