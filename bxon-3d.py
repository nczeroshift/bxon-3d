#!/usr/local/bin/python
# -*- coding: utf-8 -*-

# ##### BEGIN ZLIB LICENSE BLOCK #####
#
# Copyright (c) 2016 Luis F.Loureiro
#
# This software is provided 'as-is', without any express or implied
# warranty. In no event will the authors be held liable for any damages
# arising from the use of this software.
#
# Permission is granted to anyone to use this software for any purpose,
# including commercial applications, and to alter it and redistribute it
# freely, subject to the following restrictions:
#
#   1. The origin of this software must not be misrepresented; you must not
#   claim that you wrote the original software. If you use this software
#   in a product, an acknowledgment in the product documentation would be
#   appreciated but is not required.

#   2. Altered source versions must be plainly marked as such, and must not be
#   misrepresented as being the original software.
#
#   3. This notice may not be removed or altered from any source
#   distribution.
#
# ##### END ZLIB LICENSE BLOCK #####

bl_info = {
    "name": "bxon-3d",
    "author": "Luis F. Loureiro",
    "version": (1, 0),
    "blender": (2, 7, 0),
    "location": "File > Export > bxon-3d (.bxon)",
    "description": "Export to bxon files",
    "warning": "",
    "wiki_url": "https://github.com/nczeroshift/bxon-3d",
    "category": "Import-Export"}
    
import bpy
import struct, time, sys, os, math, codecs
from mathutils import *
from bpy_extras.io_utils import ExportHelper
from bpy.props import *


## BXON python writer methods ##

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

## File writing context
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
            else:
                for i in range(len(val)):
                    self.file.write(struct.pack("<1f",val[i]))
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

## Native value writer            
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

## Map container    
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

## Array container
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
            self.endPos = self.startPos = self.context.tell()
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


## Object indexing classes ##
    
## Entry object in the indexed map
class bxMapEntry:
    # Stored data reference
    data = None
    # Sequence id number
    id = None
    # Array of users for this data
    users = []
    # Array of tracks for this data
    tracks = None
    
    ## Constructor.
    def __init__(self, data, id):
        self.data = data
        self.id = id
        self.users = []
        self.tracks = None

## Utility class to index Blender objects
class bxMap:
    # Dictionary atribute.
    dictionary = {}
    
    ## Constructor.
    def __init__(self):
        self.dictionary = {}
    
    ## Add a element to the dictionary.
    def add(self, data, key = None):
        d_e = bxMapEntry(data,len(self.dictionary))
        if (key):
            if (key not in self.dictionary):
                self.dictionary[key] = d_e
                return True
        else:
            name = data.name
            if (name not in self.dictionary):
                self.dictionary[name] = d_e
                return True
        return False
    
    ## Find a element in the dictionary.
    def find(self, key):
        if( key in self.dictionary):
            return self.dictionary[key]
        return None
    
    ## Return dictionary size.
    def size(self):
        return len(self.dictionary)
    
    ## Return a string with dictionary properties.
    def __str__(self):
        return "bDictionary, size = " + str(self.size())
    
    ## Return unsorted dictionary vector.
    def getNonSortedVector(self):
        vec = []
        vec.extend(range(self.size()))
        for i in self.dictionary:
            vec[self.dictionary[i].id] = self.dictionary[i]
        return vec

## Animation utility functions ##

## Utility function to enumerate objects animation tracks
def bxListAnimationData(obj):
    tracks = []
    
    if obj.animation_data != None:
        if obj.animation_data.action != None:
            action = obj.animation_data.action
            range = action.frame_range
            name = action.name
            gr = bxListActionCurves(action)
            aflag = False
            if "bones" in gr: aflag = True
            rtrack = {"name":name,"strips":[{"range":range,"groups":gr}]}
            if aflag : rtrack["armature"] = True
            tracks.append(rtrack)
                                
        if len(obj.animation_data.nla_tracks) > 0:
            for t in obj.animation_data.nla_tracks:
                name = t.name
                tstrips = []
                aflag = False
                for s in t.strips:  
                    action = s.action
                    range = action.frame_range
                    gr = bxListActionCurves(action)
                    if "bones" in gr: aflag = True
                    tstrips.append({"range":range,"groups":gr})
                rtrack = {"name":name,"strips":tstrips}
                if aflag: rtrack["armature"] = True
                tracks.append(rtrack)
    return tracks


## Utility function to enumerate animation curves  
def bxListActionCurves(action):
    k_pos = None 
    k_rot = None 
    k_quat = None
    k_scale = None
    k_bones = {}
    
    for c in action.fcurves:
        path = c.data_path   
        idx = c.array_index
    
        kf = []
        for k in c.keyframe_points:
            kf.append([k.handle_left,k.co,k.handle_right])
        
        bone_name = None
        if path.startswith("pose.bones"):
            tmp = path.split("\"].")
            bone_name = tmp[0].split("[\"")[1]
            path = tmp[1]
            if not bone_name in k_bones: 
                k_bones[bone_name] = {}
                k_bones[bone_name]["position"] = None
                k_bones[bone_name]["euler"] = None
                k_bones[bone_name]["quat"] = None
                k_bones[bone_name]["scale"] = None
                
        if path == "location":
            if bone_name != None:
                if k_bones[bone_name]["position"] == None :
                    k_bones[bone_name]["position"] = [1,1,1]
                k_bones[bone_name]["position"][idx] = kf
            else:    
                if k_pos == None : k_pos = [1,1,1]
                k_pos[idx] = kf
        elif path == "rotation_euler":
            if bone_name != None:
                if k_bones[bone_name]["euler"] == None :
                    k_bones[bone_name]["euler"] = [1,1,1]
                k_bones[bone_name]["euler"][idx] = kf
            else:
                if k_rot == None : k_rot = [1,1,1]
                k_rot[idx] = kf
        elif path == "rotation_quaternion":
            nIdx = idx;
            if nIdx == 0:nIdx = 3;
            elif nIdx == 1:nIdx = 0;
            elif nIdx == 2:nIdx = 1;
            elif nIdx == 3:nIdx = 2;
            if bone_name != None:
                if k_bones[bone_name]["quat"] == None :
                    k_bones[bone_name]["quat"] = [1,1,1,1]
                k_bones[bone_name]["quat"][nIdx] = kf
            else:
                if k_quat == None : k_quat= [1,1,1,1]
                k_quat[nIdx] = kf
        elif path == "scale":
            if bone_name != None:
                if k_bones[bone_name]["scale"] == None :
                    k_bones[bone_name]["scale"] = [1,1,1]
                k_bones[bone_name]["scale"][idx] = kf
            else:
                if k_scale == None : k_scale = [1,1,1]
                k_scale[idx] = kf 
    
    ret = {}
    if k_pos != None: ret["position"] = k_pos
    if k_rot != None: ret["euler"] = k_rot
    if k_scale != None: ret["scale"] = k_scale
    if len(k_bones) > 0: ret["bones"] = k_bones
    return ret

## BXON exporter ##

class bxExporter:

    ## Constructor.
    def __init__(self):
        self.objectMap = bxMap()
        self.meshMap = bxMap()
        self.materialMap = bxMap()
        self.textureMap = bxMap()
        self.lampMap = bxMap()
        self.armatureMap = bxMap()
        self.cameraMap = bxMap()
        self.curveMap = bxMap()
    
    ## Get unique selected elements.
    def getSelected(self):                
        for o in bpy.context.selected_objects:
            add_obj = False
            if(o.type == "MESH"):
                add_obj = True
                mesh = o.data
                if ( self.meshMap.add(mesh) ):
                    for m in mesh.materials:
                        if m!= None:
                            # Get shared materials
                            if ( self.materialMap.add(m) ):
                                for tname in m.texture_slots.keys():
                                    t = m.texture_slots[tname]
                                    if(t.texture.type=="IMAGE"):
                                        self.textureMap.add(t.texture)
                element = self.meshMap.find(mesh.name)
                element.users.append(o)          
            elif(o.type == "LAMP"):
                add_obj = True
                self.lampMap.add(o.data)
                element = self.lampMap.find(o.data.name)
                element.users.append(o)
            elif(o.type == "CAMERA"):
                add_obj = True
                self.cameraMap.add(o.data)
                element = self.cameraMap.find(o.data.name)
                element.users.append(o)
            elif(o.type == "ARMATURE"):
                add_obj = True
                self.armatureMap.add(o.data)
                element = self.armatureMap.find(o.data.name)
                element.users.append(o)
            elif(o.type == "CURVE"):
                add_obj = True
                self.curveMap.add(o.data)
                element = self.curveMap.find(o.data.name)
                element.users.append(o)
            elif(o.type == "EMPTY"):
                add_obj = True
                                
            if(add_obj):
                self.objectMap.add(o)
                element = self.objectMap.find(o.name)
                atracks = bxListAnimationData(o)
                if len(atracks) > 0:
                    element.tracks = atracks
      
        print (" Selection")
        print ("  Objects : " + str(self.objectMap.size()))
        print ("  Meshs : " + str(self.meshMap.size()))
        print ("  Materials : " + str(self.materialMap.size()))    
        print ("  Textures : " + str(self.textureMap.size()))
        print ("  Cameras : " + str(self.cameraMap.size()))
        print ("  Lamps : " + str(self.lampMap.size()))
        print ("  Armatures : " + str(self.armatureMap.size()))
        print ("  Curves : " + str(self.curveMap.size()))
    
    ## Write texture data.
    def exportTexture(self, array, entry):
        tex = entry.data
        print("  Texture : \"" + tex.name + "\"")
        node = array.push(bxon_map())#map.put(tex.name,bxon_map())
        node.put("name", tex.name)
        node.put("type", "image")
        node.put("filename", os.path.basename(tex.image.filepath))
        return True

    ## Export texture mapping mode.
    def exportTextureMapping(self, array, slot):
        node = array.push(bxon_map())
        node.put("name",slot.name)
        
        mapping = "uv"
        if(slot.texture_coords == "GLOBAL"):
            mapping = "global"
        elif(slot.texture_coords == "STRAND"):
            mapping = "strand"
        elif(slot.texture_coords == "REFLECTION"):
            mapping = "refletion"     
        
        node.put("mapping", mapping)
        
        projection = "flat"
        if(slot.mapping == "CUBE"):
            projection = "cube"
        elif (slot.mapping == "TUBE"):
            projection = "tube"
        elif (slot.mapping == "SPHERE"):
            projection = "sphere"
        
        node.put("projection", projection)

        offset = node.put("offset", bxon_array(nType=BXON_FLOAT, nCount = 1, nStride = 3))
        offset.push(slot.offset)
        
        scale = node.put("scale", bxon_array(nType=BXON_FLOAT, nCount = 1, nStride = 3))
        scale.push(slot.scale)
                        
        if len(slot.uv_layer) > 0:
            node.put("uv_layer", slot.uv_layer)
              
        props = node.put("properties", bxon_map())
        
        if(slot.use_map_color_diffuse):
            props.put("diffuse_color_factor", slot.diffuse_color_factor)
            
        if(slot.use_map_alpha):
            props.put("alpha_factor", slot.alpha_factor)   
                
        if(slot.use_map_diffuse):
            props.put("diffuse_factor", slot.diffuse_factor) 
                     
        if(slot.use_map_translucency):
            props.put("translucency_factor", slot.translucency_factor) 

        if(slot.use_map_specular):
            props.put("specular_factor", slot.specular_factor) 
            
        if(slot.use_map_color_spec):
            props.put("specular_color_factor", slot.specular_color_factor) 
         
        if(slot.use_map_hardness):
            props.put("hardness_factor", slot.hardness_factor) 
         
        if(slot.use_map_normal):
            props.put("normal_factor", slot.normal_factor) 
           
        if(slot.use_map_displacement):
            props.put("displacement_factor", slot.displacement_factor) 
        
        if(slot.texture.type == "IMAGE"):
            nd = self.textureMap.find(slot.texture.name)
            if not nd:
                print ("   Error : Texture was not found.")
                return False
            node.put("texture", slot.texture.name)
            node.put("id", nd.id)
        else:
            print("   Error : Texture type isn't supported.")
            return False
        return True
        
    ## Write material data.
    def exportMaterial(self, array, entry):
        mat = entry.data
        print("  Material : \"" + mat.name + "\"")
        #node = map.put(mat.name,bxon_map())
        
        node = array.push(bxon_map())
        node.put("name",mat.name)
        
        diffuse = node.put("diffuse", bxon_array(nType=BXON_FLOAT, nCount = 1, nStride = 3))
        diffuse.push(mat.diffuse_color)
       
        node.put("alpha",mat.alpha)
        
        specular = node.put("specular", bxon_array(nType=BXON_FLOAT, nCount = 1, nStride = 3))
        specular.push(mat.specular_color)

        node.put("diffuse_intensity",mat.diffuse_intensity)
        node.put("specular_intensity",mat.specular_intensity)
        node.put("specular_hardness",mat.specular_hardness)
        
        node.put("ambient",mat.ambient)
        
        if(mat.use_transparency):
            if(mat.transparency_method == "Z_TRANSPARENCY"):
                node.put("transparency_method","alpha_blend")
        
        tex = node.put("textures",bxon_array())
        
        for tname in mat.texture_slots.keys():
            t = mat.texture_slots[tname]
            if(t.texture.type=="IMAGE"):
                 self.exportTextureMapping(tex,t)   
        return True

    ## Write camera data.    
    def exportCamera(self, array, entry):
        cam = entry.data
        print("  Camera : \"" + cam.name + "\"")
        #node = map.put(cam.name, bxon_map())
        node = array.push(bxon_map())
        node.put("name",cam.name)
        node.put("fov",(180/math.pi)*2*math.atan(16/(cam.lens* 1.3254834)))
        node.put("start", cam.clip_start)
        node.put("end", cam.clip_end)
        return True
        
    ## Write lamp data.
    def exportLamp(self, array, entry):
        lamp = entry.data
        print("  Lamp : \"" + lamp.name + "\"")
        #node = map.put(lamp.name, bxon_map())
        node = array.push(bxon_map())
        node.put("name",lamp.name)
        diffuse = node.put("color", bxon_array(nType=BXON_FLOAT, nCount = 1, nStride = 3))
        diffuse.push(lamp.color)
        node.put("energy", lamp.energy)
        node.put("distance", lamp.distance)                
        return True
        
    ## Write timeline markers
    def exportMarkers(self, node):
        markers = bpy.context.scene.timeline_markers
        if(len(markers) > 0):
            array = node.put("tl_markers", bxon_array())
            for m in markers:
                entry = array.push(bxon_map())
                entry.put("frame",m.frame)
                if(m.camera != None):
                    entry.put("camera",m.camera.name)
        return True
        
    ## Write curve data.
    def exportCurve(self, array, entry):
        curve = entry.data
        print("  Curve : \"" + curve.name + "\"")
        #node = pNode.put(curve.name, bxon_map())
        node = array.push(bxon_map())
        node.put("name",curve.name)
        node.put("resolution", curve.resolution_u)
        splines = node.put("splines", bxon_array())
        for sp in curve.splines:
            bezNode = splines.push(bxon_map())
            count = len(sp.bezier_points)
            left = bezNode.put("left", bxon_array(nType=BXON_FLOAT, nCount = count, nStride = 3))
            center = bezNode.put("center", bxon_array(nType=BXON_FLOAT, nCount = count, nStride = 3))
            right = bezNode.put("right", bxon_array(nType=BXON_FLOAT, nCount = count, nStride = 3))
            for p in sp.bezier_points:
                left.push(p.handle_left)
                center.push(p.co)
                right.push(p.handle_right)       
        return True
    
    def exportGraphGroup(self, groups, nStrip):
        if("euler" in groups and groups["euler"] != None):
            points = groups["euler"]
            nEuler = nStrip.put("euler",bxon_array())
            self.exportGraph(points,nEuler)
            
        if("scale" in groups and groups["euler"] != None):
            points = groups["scale"]
            nScale = nStrip.put("scale",bxon_array())
            self.exportGraph(points,nScale)
            
        if("quat" in groups and groups["quat"] != None):
            points = groups["quat"]
            nQuat = nStrip.put("quat",bxon_array())
            self.exportGraph(points, nQuat)
            
        if("position" in groups and groups["position"] != None):
            points = groups["position"]
            nPosition = nStrip.put("position",bxon_array())
            self.exportGraph(points, nPosition)
                            
                            
    def exportGraph(self, points, array):
        for k in range(len(points)):
            nKeyframes = array.push(bxon_array(nType = BXON_FLOAT, nCount = 3 * len(points[k]) , nStride = 2))
            for m in range(len(points[k])):
                pnt = points[k][m]
                nKeyframes.push(pnt[0])
                nKeyframes.push(pnt[1])
                nKeyframes.push(pnt[2])
                                
    def exportAnimation(self, node, tracks, armature = False):
        nTracks = node.put("tracks", bxon_array())
        
        for i in range(len(tracks)):
            track = tracks[i]
            strips = track["strips"];
                
            nTrack = nTracks.push(bxon_map())
            
            nTrack.put("name",track["name"])              
            nStrips = nTrack.put("strips",bxon_array())

            for s in range(len(strips)):
                strip = strips[s]
                groups = strip["groups"]
                
                nStrip = nStrips.push(bxon_map())
                
                if armature:
                    if "bones" in groups:
                        bones = groups["bones"]                     
                        for b in bones:
                            boneGraphs = nStrip.put(b,bxon_map())
                            bData = bones[b]
                            boneGraphs.put("range",bxon_array(nType=BXON_FLOAT, nCount = 1, nStride = 2)).push(strip["range"])
                            self.exportGraphGroup(bData, boneGraphs)  
                else: 
                    nStrip.put("range",bxon_array(nType=BXON_FLOAT, nCount = 1, nStride = 2)).push(strip["range"])
                    self.exportGraphGroup(groups, nStrip)
                         
    ## Write armature data.
    def exportArmature(self, array, entry):
        arm = entry.data
        print("  Armature : \"" + arm.name + "\"")
        node = array.push(bxon_map())
        node.put("name", arm.name)
        
        bonesMap = bxMap()
            
        for b_k in arm.bones.keys():
            bonesMap.add(arm.bones[b_k])
        
        bones = node.put("bones", bxon_array())
        
        for b_k in arm.bones.keys():
            b = arm.bones[b_k]
            
            bp_head = Vector()
            bp_tail = Vector()
            
            bNode = bones.push(bxon_map())
            
            bNode.put("name",b.name)
            
            bp_node = None    
            if(b.parent):
                bp_node = bonesMap.find(b.parent.name)
                
            if(bp_node):
                bp_head = bp_node.data.head_local
                bp_tail = bp_node.data.tail_local
                pMap = bNode.put("parent", bxon_map())
                pMap.put("name",b.parent.name)
                pMap.put("id",bp_node.id)
                          
            head = b.head_local-bp_tail
            tail = b.tail_local-bp_tail
            
            ml = bNode.put("bMatrix", bxon_array(nType = BXON_FLOAT, nCount = 1, nStride = 16))
            mf = []
            for i in range(4):
                for j in range(4):
                    mf.append(b.matrix_local[j][i])
            ml.push(mf)
            
            h = bNode.put("head", bxon_array(nType = BXON_FLOAT, nCount = 1, nStride = 3))
            h.push(head)

            t = bNode.put("tail", bxon_array(nType=BXON_FLOAT, nCount = 1, nStride = 3))
            t.push(tail)
        
        for o in entry.users:
            oEntry = self.objectMap.find(o.name)
            if(oEntry.tracks != None):
                self.exportAnimation(node.put("animation",bxon_map()), oEntry.tracks, True)
            
        return True
        
    # Write object data.    
    def exportObject(self, array, entry):
        obj = entry.data
        print("  Object : \"" + obj.name + "\"")
        #node = map.put(obj.name, bxon_map())
        node = array.push(bxon_map())
        node.put("name", obj.name)
        
        datablock_type = None
        datablock_id = None
        datablock_name = None
        
        if (obj.type == "MESH"):
            datablock_type = "mesh"
            datablock_name = obj.data.name
            datablock_id = self.meshMap.find(obj.data.name).id      
                
        elif (obj.type == "EMPTY"):
            datablock_type = "empty"
            
        elif (obj.type == "LAMP"):
            datablock_type = "lamp"
            datablock_name = obj.data.name
            datablock_id = self.lampMap.find(obj.data.name).id
            
        elif (obj.type == "CAMERA"):
            datablock_type = "camera"
            datablock_name = obj.data.name
            datablock_id = self.cameraMap.find(obj.data.name).id
            
        elif (obj.type == "CURVE"):
            datablock_type = "curve"
            datablock_name = obj.data.name
            datablock_id = self.curveMap.find(obj.data.name).id
                     
        elif (obj.type == "ARMATURE"):
            datablock_type = "armature"
            datablock_name = obj.data.name
            datablock_id = self.armatureMap.find(obj.data.name).id

        datablock = node.put("datablock", bxon_map())
        datablock.put("type", datablock_type)
        
        if(datablock_id != None):
            datablock.put("id", datablock_id)
        
        if(datablock_name != None):
            datablock.put("name", datablock_name)
            
        if(obj.parent != None):
            no = self.objectMap.find(obj.parent.name)
            if(no):
                node.put("parent", obj.parent.name)
            else:
                print("   Error : Parent object not found.")
                return False
        
        obj_mat = obj.matrix_local
        
        if(obj.parent):
            obj_mat = Matrix(obj_mat * obj.matrix_parent_inverse)
        
        position = node.put("position", bxon_array(nType=BXON_FLOAT, nCount = 1, nStride = 3))
        position.push(obj_mat.to_translation())
            
        rotation = node.put("quaternion", bxon_array(nType=BXON_FLOAT, nCount = 1, nStride = 4))
        rotation.push([obj_mat.to_quaternion().x,obj_mat.to_quaternion().y,obj_mat.to_quaternion().z,obj_mat.to_quaternion().w])
        
        scale = node.put("scale", bxon_array(nType=BXON_FLOAT, nCount = 1, nStride = 3))
        scale.push(obj_mat.to_scale())
        
        if entry.tracks != None:
            self.exportAnimation(node.put("animation",bxon_map()),entry.tracks)
            
        return True
            
    def exportMesh(self, array, entry):
        obj = entry.users[0]
        mesh = entry.data;
        
        print("  Mesh : \"" + mesh.name + "\"")
        mesh = obj.data
        
        #node = map.put(mesh.name,bxon_map())
        node = array.push(bxon_map())
        node.put("name", mesh.name)
        
        vCount = len(mesh.vertices)
        mPositions = node.put("positions", bxon_array(nType=BXON_FLOAT, nCount = vCount, nStride = 3))
        mNormals = node.put("normals", bxon_array(nType=BXON_FLOAT, nCount = vCount, nStride = 3))

        for v in mesh.vertices:
            mPositions.push(v.co)
            
        for v in mesh.vertices: 
            mNormals.push(v.normal)

        f3Count = 0
        f4Count = 0
        matCount = len(mesh.materials)
        uvCount = len(mesh.uv_textures)
        colorCount = len(mesh.vertex_colors)
        groupsCount = len(obj.vertex_groups)

        for i,fc in enumerate(mesh.polygons):
            vLen = len(fc.vertices)
            if vLen == 3:
                f3Count += 1
            elif vLen == 4:
                f4Count += 1
                
        if matCount > 0:
            mMaterials = node.put("materials",bxon_array())   
            for m in mesh.materials:
                mMaterials.push(bxon_native(BXON_STRING,m.name))
                
        if groupsCount > 0:
            mGroups = node.put("vertex_groups",bxon_array())   
            for g in obj.vertex_groups:
                mGroups.push(bxon_native(BXON_STRING,g.name))
                print(g.name)
                
            mWeights = node.put("vertex_weights",bxon_array())       
            for i,v in enumerate(mesh.vertices):
                mVW = mWeights.push(bxon_array())
                for group in v.groups:
                    mVW.push(bxon_native(BXON_INT,group.group))
                    mVW.push(bxon_native(BXON_FLOAT,group.weight))  
                    
            if obj.parent != None and obj.parent.type == "ARMATURE":
                pArmature = obj.parent.data
                node.put("armature", pArmature.name)  
                
        mFaces = node.put("faces_vertices",bxon_array(nType=BXON_INT,nCount = (f3Count + f4Count), nStride = 4))
        for i,fc in enumerate(mesh.polygons):
            if len(fc.vertices) == 3:
                mFaces.push([fc.vertices[0],fc.vertices[1],fc.vertices[2],-1])
            elif len(fc.vertices) == 4:
                mFaces.push(fc.vertices)

        if matCount > 1:
            mFm = node.put("faces_materials",bxon_array(nType=BXON_INT,nCount = (f3Count + f4Count)))
            for i,fc in enumerate(mesh.polygons):
                if len(fc.vertices) == 3 or len(fc.vertices) == 4:
                    mFm.push(fc.material_index)

        if uvCount > 0:
                mUVLayers = node.put("uv_layers",bxon_array())
                for lName in mesh.uv_textures:
                    mUVLayers.push(bxon_native(BXON_STRING,lName.name))
                    
                mFuv = node.put("faces_uv",bxon_array(nType=BXON_FLOAT, nCount = uvCount * (f3Count * 3 + f4Count * 4), nStride = 2))
                for i,fc in enumerate(mesh.polygons):
                    if len(fc.vertices) == 3 or len(fc.vertices) == 4: 
                        for k,v in enumerate(fc.vertices):
                            for j in range(uvCount):
                                uv = mesh.uv_layers[j].data[fc.loop_indices[k]].uv
                                mFuv.push([uv[0],-uv[1]])

        return True
                     
    def export(self, pNode):
        obj_vector = self.objectMap.getNonSortedVector()
        mesh_vector = self.meshMap.getNonSortedVector()
        material_vector = self.materialMap.getNonSortedVector()
        texture_vector = self.textureMap.getNonSortedVector()
        armature_vector = self.armatureMap.getNonSortedVector()
        lamp_vector = self.lampMap.getNonSortedVector()
        camera_vector = self.cameraMap.getNonSortedVector()    
        curve_vector = self.curveMap.getNonSortedVector()    
        
        if(texture_vector != None):
            array = pNode.put("texture", bxon_array())
            for t in texture_vector:
                if not(self.exportTexture(array, t)):
                    print("   Error")
                    return False
                
        if(material_vector != None):
            array = pNode.put("material", bxon_array())
            for m in material_vector:
                if not(self.exportMaterial(array, m)):
                    print("   Error")
                    return False
                                                    
        if(mesh_vector != None):
            array = pNode.put("mesh", bxon_array())
            for m in mesh_vector:
                if not(self.exportMesh(array, m)):
                    print("   Error")
                    return False
                                
        if(camera_vector != None):
            array = pNode.put("camera", bxon_array())
            for c in camera_vector:
                if not(self.exportCamera(array, c)):
                    print("   Error")
                    return False
                
        if(armature_vector != None):
            array = pNode.put("armature", bxon_array())
            for a in armature_vector:
                #ue = []
                #for u in a[1].users:
                #    ue.append(self.objectMap.find(u.name))
                if not(self.exportArmature(array,a)):
                    return False                    

        if(curve_vector != None):
            array = pNode.put("curve", bxon_array())
            for a in curve_vector:
                if not(self.exportCurve(array, a)):
                    return False    
                    
        if(lamp_vector != None):
            array = pNode.put("lamp", bxon_array())
            for a in lamp_vector:
                if not(self.exportLamp(array, a)):
                    return False    
                                          
        if(obj_vector != None):
            array = pNode.put("object", bxon_array())
            for o in obj_vector:
                if not(self.exportObject(array,o)):
                    return False

        self.exportMarkers(pNode)
        
def runExport(filename):
    print("\nbxon-3d start, " + time.ctime())
    start_time = time.time()

    f = open(filename,"wb")
    ctx = bxon_context(f)

    root = bxon_map(ctx)

    bx = bxExporter()

    bx.getSelected()

    print("\n Exporting")
    bx.export(root)
    
    root.flush()
    f.close()

    elapsed_time = time.time() - start_time
    print("\n Time: " + str(math.floor(elapsed_time*1000)) + " ms")
    print("bxon-3d end")

###### EXPORT OPERATOR #######
class export_bxon(bpy.types.Operator, ExportHelper):
    '''Exports selected objects as bxon-3d file'''
    bl_idname = "bxon.export"
    bl_label = "Export"
    filename_ext = ".bxon"

    @classmethod
    def poll(cls, context):
        return context.active_object.type in {'MESH','CAMERA','LAMP','EMPTY','ARMATURE','CURVE'}

    def execute(self, context):
        runExport(self.filepath)
        return {'FINISHED'}
    
    def invoke(self, context, event):
        wm = context.window_manager

        if True:
            # File selector
            wm.fileselect_add(self) # will run self.execute()
            return {'RUNNING_MODAL'}
        elif True:
            # search the enum
            wm.invoke_search_popup(self)
            return {'RUNNING_MODAL'}
        elif False:
            # Redo popup
            return wm.invoke_props_popup(self, event)
        elif False:
            return self.execute(context)

def menu_func(self, context):
    self.layout.operator(export_bxon.bl_idname, text="bxon-3d (.bxon)")

def register():
    bpy.utils.register_module(__name__)
    bpy.types.INFO_MT_file_export.append(menu_func)

def unregister():
    bpy.utils.unregister_module(__name__)
    bpy.types.INFO_MT_file_export.remove(menu_func)

if __name__ == "__main__":
    #runExport("file.bxon")
    register()

