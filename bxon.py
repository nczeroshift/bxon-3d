#!/usr/local/bin/python
# -*- coding: utf-8 -*-

#BXON Python "Direct to File" Writer

import struct, time, sys, os, math, codecs

BXON_NIL        = 0
BXON_STRING     = 1
BXON_BOOLEAN    = 2
BXON_INT        = 3
BXON_LONG       = 4
BXON_FLOAT      = 5
BXON_DOUBLE     = 6
BXON_BYTE       = 7

BXON_LENGTH_8   = 0x00
BXON_LENGTH_16  = 0x10
BXON_LENGTH_32  = 0x20
BXON_LENGTH_64  = 0x30

BXON_OBJECT     = 0x00
BXON_ARRAY      = 0x40
BXON_MAP        = 0x80

class bxon_context(object):
    def __init__(self,f):
        self.file = f

    def tell(self):
        return self.file.tell()

    def seek(self,p):
        self.file.seek(p,0)

    def write(self,p,v):
        self.file.write(struct.pack(p,v))

    def close(self):
        self.file.close()

    def lengthForNative(self,t):
        if(t == BXON_FLOAT):
            return 4
        elif(t == BXON_INT):
            return 4
        elif(t == BXON_DOUBLE):
            return 8
        elif(t == BXON_LONG):
            return 8
        elif(t == BXON_BYTE):
            return 1
        elif(t == BXON_BOOLEAN):
            return 1
            
    def writeNative(self,t,s,val):
        if t == BXON_FLOAT:
            if s == 1:
                self.file.write(struct.pack("<f",val))
            elif s == 2:
                self.file.write(struct.pack("<2f",val[0],val[1]))
            elif s == 3:
                self.file.write(struct.pack("<3f",val[0],val[1],val[2]))
            elif s == 4:
                self.file.write(struct.pack("<4f",val[0],val[1],val[2],val[3]))
        elif t == BXON_INT:
            if s == 1:
                self.file.write(struct.pack("<i",val))
            elif s == 2:
                self.file.write(struct.pack("<2i",val[0],val[1]))
            elif s == 3:
                self.file.write(struct.pack("<3i",val[0],val[1],val[2]))
            elif s == 4:
                self.file.write(struct.pack("<4i",val[0],val[1],val[2],val[3]))
        elif(t == BXON_LONG):
            self.write("<q",val)
        elif(t == BXON_DOUBLE):
            self.write("<d",val) 
        elif(t == BXON_BOOLEAN):
            self.write("<B",val) 
        elif(t == BXON_BYTE):
            self.write("<B",val) 
            
class bxon_native(object):
    def __init__(self, t, v = None):
        self.type = t
        self.value = v

    def write(self,ctx):
        if self.type == BXON_FLOAT:
            ctx.write("<B",BXON_FLOAT)
            ctx.write("<f",self.value)  
        elif self.type == BXON_INT:
            ctx.write("<B",BXON_INT)
            ctx.write("<i",self.value)   
        elif self.type == BXON_NIL: 
            ctx.write("<B",BXON_NIL)
        elif self.type == BXON_STRING:
            ctx.write("<B",BXON_STRING | BXON_LENGTH_32)
            data = bytearray(self.value.encode('utf-8'));
            ctx.write("<i",len(data))
            for c in data:
                ctx.file.write(struct.pack("<B",c))
        elif self.type == BXON_BOOLEAN: 
            ctx.write("<B",BXON_BOOLEAN) 
            ctx.write("<B",self.value)    
        elif self.type == BXON_LONG:
            ctx.write("<B",BXON_LONG)
            ctx.write("<q",self.value)
        elif self.type == BXON_DOUBLE:
            ctx.write("<B",BXON_DOUBLE)
            ctx.write("<d",self.value)  
        elif self.type == BXON_BYTE:
            ctx.write("<B",BXON_BYTE)
            ctx.write("<B",self.value)
    
class bxon_map(object):
    def __init__(self,ctx=None):
        self.parent = None
        self.context = ctx
        self.startPos = None
        self.endPos = None
        self.map = {}

    def write(self,p=None):
        if p != None:
            self.parent = p;
            self.context = p.context;
        
        if self.startPos == None:
            self.context.write("<B",BXON_MAP|BXON_LENGTH_64)
            self.context.write("<q",0)
            self.endPos = self.startPos = self.context.tell()

    def _update(self, pos = None):
        if(pos == None):
            pos = self.context.tell()
        self.endPos = pos
        if(self.parent != None ):
            self.parent._update(pos);

    def put(self, key, vObj):
        self.write()
        kObj = bxon_native(BXON_STRING,key);
        kObj.write(self.context)
        t = type(vObj)
        if t is bxon_native:
            vObj.write(self.context)
        elif t is str:
            bxon_native(BXON_STRING,vObj).write(self.context)
        elif t is float:
            bxon_native(BXON_FLOAT,vObj).write(self.context)
        elif t is int:
            bxon_native(BXON_INT,vObj).write(self.context)
        elif t is bool:
            bxon_native(BXON_BOOLEAN,vObj).write(self.context)
        else:
            self.map[key] = vObj;
            vObj.write(self)

        self._update();
        
        return vObj;

    def flush(self):
        for i in self.map:
            self.map[i].flush();
    
        lenght = self.endPos - self.startPos;
        self.context.seek(self.startPos-8);
        self.context.write("<q",lenght)
        self.context.seek(self.endPos);

class bxon_array(object):
    def __init__(self,ctx=None,nType=BXON_NIL,nCount=0,nStride=1):
        self.parent = None
        self.context = ctx
        self.startPos = None
        self.endPos = None
        self.nativeType = BXON_NIL;
        self.array = []
        self.stride = nStride
        
        if nType != BXON_NIL and nType != BXON_STRING:
            self.nativeType = nType
            self.nativeCount = nCount
            self.nativeIndex = 0

    def write(self,p=None):
        if p != None:
            self.parent = p;
            self.context = p.context;
        if self.startPos == None:
            self.context.write("<B",BXON_ARRAY|BXON_LENGTH_64|self.nativeType)
            self.context.write("<q",0)
            self.startPos = self.context.tell()
            if self.nativeType != BXON_NIL:
                ePos = self.startPos + self.nativeCount * self.stride * self.context.lengthForNative(self.nativeType)
                self.context.seek(ePos)
                
    def _update(self, pos = None):
        if pos == None:
            pos = self.context.tell()
        self.endPos = pos
        if self.parent != None:
            self.parent._update(pos);

    def push(self, obj):
        self.write()
        if self.nativeType != BXON_NIL:    
            pos = self.startPos + self.nativeIndex * self.stride * self.context.lengthForNative(self.nativeType)
            
            if pos!=self.context.tell():
                self.context.seek(pos)
            if type(obj) == bxon_native:
                self.context.writeNative(self.nativeType,self.stride,obj.value)
            else:
                self.context.writeNative(self.nativeType,self.stride,obj)
            
            self.nativeIndex+=1
            
            if(self.nativeIndex >= self.nativeCount):
                self._update()
        else:
            if type(obj) is bxon_native:
                obj.write(self.context)
            else:
                self.array.append(obj);
                obj.write(self)
            self._update()
        return obj

    def flush(self):
        for i in range(len(self.array)):
            self.array[i].flush();

        lenght = self.endPos - self.startPos;
        self.context.seek(self.startPos-8);
        self.context.write("<q",lenght)
        self.context.seek(self.endPos);

def test():
    print("BXON Python Writer Test")
    
    f = open("test.bxon","wb")
    ctx = bxon_context(f)
    
    start_time = time.time()
    
    # Create root object (map or array)
    root = bxon_map(ctx)

    # Test writing of default objects
    root.put(u"int_0é", bxon_native(BXON_INT, 10))
    root.put("long_1", bxon_native(BXON_LONG, 100000000))
    root.put("float_2", bxon_native(BXON_FLOAT, 10.0))
    root.put("double_3", bxon_native(BXON_DOUBLE, 12.0))
    root.put("string_4", bxon_native(BXON_STRING, "bxon string test!"))
    root.put("byte_5", bxon_native(BXON_BYTE, 0xBA))
    root.put("bool_6", bxon_native(BXON_BOOLEAN, True))
    root.put("nil_7", bxon_native(BXON_NIL))
        
    # Array object writing
    array1 = root.put("array",bxon_array())
    array1.push(bxon_native(BXON_FLOAT,1e6))
    array1.push(bxon_native(BXON_DOUBLE,1e6))
    array1.push(bxon_native(BXON_STRING,"test!"))
    
    # Map object writing
    map1 = root.put("map",bxon_map())
    map1.put("m1",bxon_native(BXON_INT,10))
    map1.put("m2",bxon_native(BXON_BYTE,0xFE))
    map1.put("m3",bxon_native(BXON_NIL))
    
    # Simulatenous array writing (native only)
    array_a = root.put("array_a",bxon_array(nType=BXON_DOUBLE,nCount = 5))
    array_b = root.put("array_b",bxon_array(nType=BXON_FLOAT,nCount = 5))
    for i in range(5):
        array_a.push(bxon_native(BXON_DOUBLE,i*10))
        array_b.push(bxon_native(BXON_FLOAT,i*10+10))

    # Finish file by writing lengths in headers
    root.flush();

    f.close();
    
    elapsed_time = time.time() - start_time
    print("Time: " + str(math.floor(elapsed_time*1000)) + " ms")
    
if __name__ == "__main__":
    test()

