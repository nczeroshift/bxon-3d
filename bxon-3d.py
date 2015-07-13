import bpy
from bxon import *
import struct, time, sys, os, math, codecs

print("BXON Start")

start_time = time.time()

f = open("test.bxon","wb")
ctx = bxon_context(f)

root = bxon_map(ctx)

meshMap = root.put("mesh",bxon_map())

obj = bpy.context.selected_objects[0]
mesh = obj.data


def writeMesh(pNode,mesh):
    node = pNode.put(mesh.name,bxon_map())
    
    vCount = len(mesh.vertices)
    mPositions = node.put("positions",bxon_array(nType=BXON_FLOAT, nCount = vCount, nStride = 3))
    mNormals = node.put("normals",bxon_array(nType=BXON_FLOAT, nCount = vCount, nStride = 3))
    
    for v in mesh.vertices:
        mPositions.push(v.co)
        
    for v in mesh.vertices: 
        mNormals.push(v.normal)
    
    f3Count = 0
    f4Count = 0
    matCount = len(mesh.materials)
    uvCount = len(mesh.uv_textures)
    colorCount = len(mesh.vertex_colors)
    
    for i,fc in enumerate(mesh.polygons):
        vLen = len(fc.vertices)
        if vLen == 3:
            f3Count += 1
        elif vLen == 4:
            f4Count += 1

    #for i,fc in enumerate(mesh.polygons):
    #    print(fc)

       
    if f3Count > 0:
        mF3 = node.put("faces3",bxon_array(nType=BXON_INT,nCount = f3Count, nStride = 3))
        for i,fc in enumerate(mesh.polygons):
            vLen = len(fc.vertices)
            if vLen == 3:
                mF3.push(fc.vertices)            
        
        if matCount > 1:
            mF3m = node.put("faces3mat",bxon_array(nType=BXON_INT, nCount = f3Count ))
            for i,fc in enumerate(mesh.polygons):
                if len(fc.vertices) == 3:
                    mF3m.push(fc.material_index)

        if uvCount > 0:
            mF3uv = node.put("faces3uv",bxon_array(nType=BXON_FLOAT, nCount = f3Count * uvCount * 3, nStride = 2))
            for i,fc in enumerate(mesh.polygons):
                if len(fc.vertices) == 3:
                    for k,v in enumerate(fc.vertices):
                        for j in range(uvCount):
                            mF3uv.push(mesh.uv_layers[j].data[fc.loop_indices[k]].uv)
     
    if f4Count > 0:
        mF4 = node.put("faces4",bxon_array(nType=BXON_INT, nCount = f4Count, nStride = 4))
        for i,fc in enumerate(mesh.polygons):
            vLen = len(fc.vertices)
            if vLen == 4:
                mF4.push(fc.vertices) 
        
        if matCount > 1:
            mF4m = node.put("faces4mat",bxon_array(nType=BXON_INT, nCount = f4Count ))
            for i,fc in enumerate(mesh.polygons):
                if len(fc.vertices) == 4:
                    mF4m.push(fc.material_index)
                    
        if uvCount > 0:
            mF4uv = node.put("faces4uv",bxon_array(nType=BXON_FLOAT, nCount = f4Count * uvCount * 4, nStride = 2))
            for i,fc in enumerate(mesh.polygons):
                if len(fc.vertices) == 4:
                    for k,v in enumerate(fc.vertices):
                        for j in range(uvCount):
                            mF4uv.push(mesh.uv_layers[j].data[fc.loop_indices[k]].uv)
                 
             
writeMesh(meshMap,mesh)


elapsed_time = time.time() - start_time
print(" Time: " + str(math.floor(elapsed_time*1000)) + " ms")

start_time = time.time() 
print("BXON Flushing")

root.flush()

elapsed_time = time.time() - start_time
print(" Time: " + str(math.floor(elapsed_time*1000)) + " ms")

f.close()

print("BXON End")

