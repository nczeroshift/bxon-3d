# ##### BEGIN ZLIB LICENSE BLOCK #####
#
# Copyright (c) 2012 Luis F.Loureiro
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
    "name": "bXporter",
    "author": "Luis F. Loureiro",
    "version": (1, 0),
    "blender": (2, 6, 3),
    "location": "File > Export > bXporter (.bx)",
    "description": "Export to bXporter files (.bx)",
    "warning": "",
    "wiki_url": "code.google.com/p/nctoolkit",
    "category": "Import-Export"}

import bpy
import struct, time, sys, os, subprocess, math
from mathutils import *
from bpy_extras.io_utils import ExportHelper
from bpy.props import *

bx_optimizer_default_filename = "set_filename_to_bx_optimizer"    
bx_report_timers = True

## Custom Dictionary

## Class used to store the data and the sequence id.    
class bXDictionaryElement:
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

## Data storing class based on python dictionary.
class bXDictionary:

    # Dictionary atribute.
    dictionary = {}
    
    ## Constructor.
    def __init__(self):
        self.dictionary = {}
    
    ## Add a element to the dictionary.
    ## @param key Item indentification, if None the name atribute in data 
    ## class will be used as key.
    ## @param data Class instance or item to be stored.
    def add(self,key, data = None):
        
        d_e = bXDictionaryElement(data,len(self.dictionary))
        
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
    ## @param key Element identification.
    def find(self, key):
        if( key in self.dictionary):
            return self.dictionary[key]
        return None
    
    ## Return dictionary size.
    def size(self):
        return len(self.dictionary)
    
    ## Return a string with dictionary properties.
    def __str__(self):
        return "bXDictionary, size = " + str(self.size())
    
    ## Return unsorted dictionary vector.
    def getNonSortedVector(self):
        vec = []
        vec.extend(range(self.size()))
        for i in self.dictionary:
            vec[self.dictionary[i].id] = [i,self.dictionary[i]]
        return vec

## Animation listing
def listAnimationData(obj):
    tracks = []
    
    if obj.animation_data != None:
        if obj.animation_data.action != None:
            action = obj.animation_data.action
            range = action.frame_range
            name = action.name
            gr = listActionCurves(action)
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
                    gr = listActionCurves(action)
                    if "bones" in gr: aflag = True
                    tstrips.append({"range":range,"groups":gr})
                rtrack = {"name":name,"strips":tstrips}
                if aflag: rtrack["armature"] = True
                tracks.append(rtrack)
                
    return tracks

def listActionCurves(action):
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
            if bone_name != None:
                if k_bones[bone_name]["quat"] == None :
                    k_bones[bone_name]["quat"] = [1,1,1,1]
                k_bones[bone_name]["quat"][idx] = kf
            else:
                if k_quat == None : k_quat= [1,1,1,1]
                k_quat[idx] = kf
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

## DataIO
class bXBinaryFileWriter:
    ## File stream.
    f = None
    ## Constructor.
    def __init__(self):
        self.f = None

    ## Open file stream.
    def open(self, filename):
        self.f = open(filename,"wb")
        return True

    def writeVec2(self,x,y):
        self.f.write(struct.pack("<2f",x,y))

    def writeVec3(self,x,y,z):
        self.f.write(struct.pack("<3f",x,y,z))

    def writeVec4(self,x,y,z,w):
        self.f.write(struct.pack("<4f",x,y,z,w))

    def writeCol4ub(self,x,y,z,w):
        self.f.write(struct.pack("<4B",x,y,z,w))

    def writeBool(self,val):
        self.f.write(struct.pack("<B",int(val)))

    def writeStr(self,str):
        data = str.encode("utf-8");
        self.f.write(struct.pack("<i",len(data)))
        for bd in data:
            self.f.write(struct.pack("<b",bd))

    def writeInt(self,val):
        self.f.write(struct.pack("<i",val))	

    def writeFloat(self,val):
        self.f.write(struct.pack("<f",val))	

    def close(self):
        self.f.close()


BX_GRAPH_LOC_X = 1
BX_GRAPH_LOC_Y = 2
BX_GRAPH_LOC_Z = 3
BX_GRAPH_ROT_X = 4
BX_GRAPH_ROT_Y = 5
BX_GRAPH_ROT_Z = 6
BX_GRAPH_ROT_W = 7
BX_GRAPH_SCALE_X = 8
BX_GRAPH_SCALE_Y = 9
BX_GRAPH_SCALE_Z = 10	

## bXporter exporter class.
class bXporter:


    ## Constructor.
    def __init__(self):
        self.ObjectCollection = bXDictionary()
        self.MeshCollection = bXDictionary()
        self.MaterialCollection = bXDictionary()
        self.TextureCollection = bXDictionary()
        self.LampCollection = bXDictionary()
        self.ArmatureCollection = bXDictionary()
        self.CameraCollection = bXDictionary()
        self.CurveCollection = bXDictionary()

    ## Object collection dictionary.
    ObjectCollection = None
    
    ## Mesh collection dictionary.
    MeshCollection = None
    
    ## Material collection dictionary.
    MaterialCollection = None
    
    ## Texture collection dictionary.
    TextureCollection = None
    
    ## Lamp collection dictionary.
    LampCollection = None
    
    ## Armature collection dictionary.
    ArmatureCollection = None
    
    ## Camera collection dictionary.
    CameraCollection = None
    
    ## Curve collection dictionary.
    CurveCollection = None

    
    ## Get unique selected elements.
    def getSelected(self):
        
        t1 = time.clock()
                
        for o in bpy.context.selected_objects:
            add_obj = False
            if(o.type == "MESH"):
                add_obj = True
                mesh = o.data
                # get shared meshs
                if ( self.MeshCollection.add(None,mesh) ):
                    for m in mesh.materials:
                        if m!= None:
                            # get shared materials
                            if ( self.MaterialCollection.add(None,m) ):
                                for tname in m.texture_slots.keys():
                                    t = m.texture_slots[tname]
                                    if(t.texture.type=="IMAGE"):
                                        self.TextureCollection.add(None,t.texture)
                element = self.MeshCollection.find(mesh.name)
                element.users.append(o)          
            elif(o.type == "LAMP"):
                add_obj = True
                self.LampCollection.add(None,o.data)
                element = self.LampCollection.find(o.data.name)
                element.users.append(o)
            elif(o.type == "CAMERA"):
                add_obj = True
                self.CameraCollection.add(None,o.data)
                element = self.CameraCollection.find(o.data.name)
                element.users.append(o)
            elif(o.type == "ARMATURE"):
                add_obj = True
                self.ArmatureCollection.add(None,o.data)
                element = self.ArmatureCollection.find(o.data.name)
                element.users.append(o)
            elif(o.type == "CURVE"):
                add_obj = True
                self.CurveCollection.add(None,o.data)
                element = self.CurveCollection.find(o.data.name)
                element.users.append(o)
            elif(o.type == "EMPTY"):
                add_obj = True
                                
            # Add object if is type is suported by bXporter.
            if(add_obj):
                self.ObjectCollection.add(None,o)
                element = self.ObjectCollection.find(o.name)
                atracks = listAnimationData(o)
                if len(atracks) > 0:
                    element.tracks = atracks
        t2 = time.clock()
        
        print (" Elements Enumeration")
        if bx_report_timers:
            print ("  Enumeration Time : " + str(round(t2 - t1,4)) + "s")
        print ("  Collection Size ")
        print ("   Objects : " + str(self.ObjectCollection.size()))
        print ("   Meshs : " + str(self.MeshCollection.size()))
        print ("   Materials : " + str(self.MaterialCollection.size()))    
        print ("   Textures : " + str(self.TextureCollection.size()))
        print ("   Cameras : " + str(self.CameraCollection.size()))
        print ("   Lamps : " + str(self.LampCollection.size()))
        print ("   Armatures : " + str(self.ArmatureCollection.size()))
        print ("   Curves : " + str(self.CurveCollection.size()))
        
    
    ## Write texture data.
    def exportTexture(self,file,tex):
        print("  Texture : \"" + tex.name +"\"")
        file.writeStr(tex.name)
        file.writeStr(os.path.basename(tex.image.filepath))
        return True

    
    ## Export texture mapping mode.
    def exportTextureMapping(self,file,slot):
        TEX_FILTER_DIFFUSE_INTENSITY     = 0
        TEX_FILTER_DIFFUSE_COLOR         = 1
        TEX_FILTER_DIFFUSE_ALPHA         = 2
        TEX_FILTER_DIFFUSE_TRANSLUCENCY  = 3
        TEX_FILTER_SPECULAR_INTENSITY    = 4
        TEX_FILTER_SPECULAR_COLOR        = 5
        TEX_FILTER_SPECULAR_HARDNESS     = 6
        TEX_FILTER_GEOMETRY_NORMAL       = 7
        TEX_FILTER_GEOMETRY_DISPLACEMENT = 8

        TEX_MAPPING_GLOBAL     = 0
        TEX_MAPPING_UV         = 1
        TEX_MAPPING_STRAND     = 2
        TEX_MAPPING_REFLECTION = 3

        TEX_PROJECTION_FLAT   = 0
        TEX_PROJECTION_CUBE   = 1
        TEX_PROJECTION_TUBE   = 2
        TEX_PROJECTION_SPHERE = 3

        file.writeStr(slot.name)

        mapping = TEX_MAPPING_UV
        if(slot.texture_coords == "GLOBAL"):
            mapping = TEX_MAPPING_GLOBAL
        elif(slot.texture_coords == "STRAND"):
            mapping = TEX_MAPPING_STRAND
        elif(slot.texture_coords == "REFLECTION"):
            mapping = TEX_MAPPING_REFLECTION     
             
        file.writeInt(mapping)
            
        projection = TEX_PROJECTION_FLAT

        if(slot.mapping == "CUBE"):
            projection = TEX_PROJECTION_CUBE
        elif (slot.mapping == "TUBE"):
            projection = TEX_PROJECTION_TUBE
        elif (slot.mapping == "SPHERE"):
            projection = TEX_PROJECTION_SPHERE

        file.writeInt(projection)

        file.writeVec3(slot.offset.x,slot.offset.y,slot.offset.z)
        file.writeVec3(slot.scale.x,slot.scale.y,slot.scale.z)
                   
        file.writeStr(slot.uv_layer)

        props = []    
        if(slot.use_map_color_diffuse):
            props.append([TEX_FILTER_DIFFUSE_COLOR,slot.diffuse_color_factor])
            
        if(slot.use_map_alpha):
            props.append([TEX_FILTER_DIFFUSE_ALPHA,slot.alpha_factor])       
                
        if(slot.use_map_diffuse):
            props.append([TEX_FILTER_DIFFUSE_INTENSITY,slot.diffuse_factor])  
                     
        if(slot.use_map_translucency):
            props.append([TEX_FILTER_DIFFUSE_INTENSITY,slot.translucency_factor])

        if(slot.use_map_specular):
            props.append([TEX_FILTER_SPECULAR_INTENSITY,slot.specular_factor])
            
        if(slot.use_map_color_spec):
            props.append([TEX_FILTER_SPECULAR_COLOR,slot.specular_color_factor])
            
        if(slot.use_map_hardness):
            props.append([TEX_FILTER_SPECULAR_HARDNESS,slot.hardness_factor])
           
        if(slot.use_map_normal):
            props.append([TEX_FILTER_GEOMETRY_NORMAL,slot.normal_factor])
            
        if(slot.use_map_displacement):
            props.append([TEX_FILTER_GEOMETRY_DISPLACEMENT,slot.displacement_factor])

        file.writeInt(len(props))
        for p in props:
            file.writeInt(p[0])
            file.writeFloat(p[1])
        
        if(slot.texture.type=="IMAGE"):
            nd = self.TextureCollection.find(slot.texture.name)
            if not nd:
                print ("   Error : Texture was not found.")
                return False
            file.writeInt(nd.id)
        else:
            print("   Error : Texture type isn't supported.")
            return False
        
        return True


    ## Write material data.
    def exportMaterial(self,file,mat):

        BX_MATERIAL_ANIMATION    = 1
        BX_MATERIAL_ALPHA        = 2
        
        print("  Material : \"" + mat.name  +"\"")

        file.writeStr(mat.name)
        
        diffColor = mat.diffuse_color
        specColor = mat.specular_color
        
        file.writeVec4(diffColor.r,diffColor.g,diffColor.b,mat.alpha)
        file.writeVec4(specColor.r,specColor.g,specColor.b,1)
        file.writeFloat(mat.diffuse_intensity)
        file.writeFloat(mat.specular_intensity)
        file.writeFloat(mat.ambient)
        
        params = 0
        if(mat.transparency_method == "Z_TRANSPARENCY"):
            params += BX_MATERIAL_ALPHA
            
        file.writeInt(params)
        
        exportTex = []
        maxTextures = 0
        for tname in mat.texture_slots.keys():
            t = mat.texture_slots[tname]
            if(t.texture.type=="IMAGE"):
                maxTextures+=1
                exportTex.append(t)

        file.writeInt(maxTextures)
        
        for tex in exportTex:
            self.exportTextureMapping(file,tex)
           
        return True

    
    ## Write camera data.    
    def exportCamera(self,file,cam):
        print("  Camera : \"" + cam.name +"\"")
        file.writeStr(cam.name)
        file.writeFloat((180/math.pi)*2*math.atan(16/(cam.lens* 1.3254834)))
        file.writeFloat(cam.clip_start)
        file.writeFloat(cam.clip_end)
        return True

    
    ## Write lamp data.
    def exportLamp(self,file,lamp):
        print("  Lamp : \"" + lamp.name +"\"")
        file.writeStr(lamp.name)
        file.writeVec3(lamp.color.r,lamp.color.g,lamp.color.b)
        file.writeFloat(lamp.energy)
        file.writeFloat(lamp.distance)                
        return True

    
    ## Write curve data.
    def exportCurve(self,file,curve):
        print("  Curve : \"" + curve.name +"\"")
        file.writeStr(curve.name)
        file.writeInt(curve.resolution_u)
        file.writeInt(len(curve.splines))
        for sp in curve.splines:
            file.writeInt(len(sp.bezier_points))
            for p in sp.bezier_points:
                file.writeVec3(p.handle_left.x,p.handle_left.y,p.handle_left.z)
                file.writeVec3(p.co.x,p.co.y,p.co.z)
                file.writeVec3(p.handle_right.x,p.handle_right.y,p.handle_right.z)
                
        return True

    
    ## Write armature data.
    def exportArmature(self,file,arm,users):
        print("  Armature : \"" + arm.name +"\"")
        file.writeStr(arm.name)
        
        BonesCollection = bXDictionary()
            
        for b_k in arm.bones.keys():
            BonesCollection.add(None,arm.bones[b_k])
        
        file.writeInt(BonesCollection.size())
        
        for b_k in arm.bones.keys():
            b = arm.bones[b_k]
            
            file.writeStr(b.name)
           
            bp_node = None
            
            bp_head = Vector()
            bp_tail = Vector()
                
            if(b.parent):
                bp_node = BonesCollection.find(b.parent.name)
                
            if(bp_node):
                bp_head = bp_node.data.head_local
                bp_tail = bp_node.data.tail_local
                file.writeInt(bp_node.id)
            else:
                file.writeInt(-1)
                
            head = b.head_local-bp_tail
            tail = b.tail_local-bp_tail
            
            file.writeVec3(head.x,head.y,head.z)
            file.writeVec3(tail.x,tail.y,tail.z)
        
        self.exportArmatureAnimation(file,arm,users)
        
        return True
    
    def exportArmatureAnimation(self,file,arm,users):
        tmpTracks = []
        for u in users:
            if u.tracks == None:
                continue
            for i in range(len(u.tracks)):
                if "armature" in u.tracks[i]:
                    tmpTracks.append(u.tracks[i])
                        
        file.writeInt(len(tmpTracks))
        
        print("   Tracks : "+str(len(tmpTracks))) 
        
        for t in tmpTracks:
            file.writeStr(t["name"])
            file.writeInt(len(t["strips"]))
            
            print("    Track : \""+t["name"]+"\"")
            print("    Strips : "+str(len(t["strips"])))    
             
            for s in t["strips"]:
                file.writeVec2(s["range"].x,s["range"].y)
                print("     Range : ["+ str(s["range"].x)+", "+str(s["range"].y)+"]")
                
                bones = s["groups"]["bones"]
                
                bonescount = len(bones)
                print("     Bones : "+str(bonescount)) 
                file.writeInt(bonescount)
                
                for b in bones:
                    bone = bones[b]
                    file.writeStr(b)
                    print("      Bone : "+b)
                    graphsCount = 0
                    
                    for g in bone:
                        graph = bone[g]
                        if graph != None:
                            graphsCount += len(graph)
                    
                    file.writeInt(graphsCount)

                    for g in bone:
                        graph = bone[g]
                        if graph == None:
                            continue
                        
                        gcount = len(graph)
                        kf = [None,None,None,None]
                        val_transform = [[],[],[],[]]
                        axis_codes = None
                                    
                        print("       Type : "+g)
                        
                        kf[0] = graph[0]
                        kf[1] = graph[1]
                        kf[2] = graph[2]
                        
                        if gcount == 4:
                            kf[3] = graph[3]
                                              
                        if len(graph[0]) != len(graph[1]) or len(graph[1]) != len(graph[2]):
                            print("Error, different number of keyframes in axis")
                            return False

                        kfcount = len(graph[0])
                        print("      Keyframes : "+str(kfcount))
                          
                        # Perform inverse transform ?
                        for i in range(kfcount):
                            kx = kf[0][i];
                            ky = kf[1][i];
                            kz = kf[2][i];
                            kw = None
                            
                            if kf[3] != None:
                                kw = kf[3][i]
                                    
                            time_left = kx[0].x
                            time_center = kx[1].x
                            time_right = kx[2].x
                           
                            val_left = [kx[0].y,ky[0].y,kz[0].y]
                            val_center = [kx[1].y,ky[1].y,kz[1].y]
                            val_right = [kx[2].y,ky[2].y,kz[2].y]
                            
                            if kf[3] != None:
                                 val_left.append(kw[0].y)
                                 val_center.append(kw[1].y)
                                 val_right.append(kw[2].y)
                            
                            val_left = Vector(val_left)
                            val_center = Vector(val_center)
                            val_right = Vector(val_right)                            
                                                                                
                            val_transform[0].append([[time_left,val_left.x],[time_center,val_center.x],[time_right,val_right.x]])
                            val_transform[1].append([[time_left,val_left.y],[time_center,val_center.y],[time_right,val_right.y]])
                            val_transform[2].append([[time_left,val_left.z],[time_center,val_center.z],[time_right,val_right.z]])
                            
                            if kf[3] != None:
                                val_transform[3].append([[time_left,val_left.w],[time_center,val_center.w],[time_right,val_right.w]])

                            if g == "position":
                                axis_codes = [BX_GRAPH_LOC_X,BX_GRAPH_LOC_Y,BX_GRAPH_LOC_Z]
                            elif g == "quat":
                                axis_codes = [BX_GRAPH_ROT_X,BX_GRAPH_ROT_Y,BX_GRAPH_ROT_Z,BX_GRAPH_ROT_W]
                            elif g == "scale":
                                axis_codes = [BX_GRAPH_SCALE_X,BX_GRAPH_SCALE_Y,BX_GRAPH_SCALE_Z]
                            else:
                                print("Error, unknown graph group name")
                                return False

                        for iaxis in range(gcount):
                            file.writeInt(axis_codes[iaxis]) # graph type
                            kfcount = len(val_transform[iaxis])
                            file.writeInt(kfcount) # number of keyframes
                            for ikeyframe in range(kfcount):
                                v = val_transform[iaxis][ikeyframe]
                                file.writeFloat(v[0][0])
                                file.writeFloat(v[0][1])
                                file.writeFloat(v[1][0])
                                file.writeFloat(v[1][1])
                                file.writeFloat(v[2][0])
                                file.writeFloat(v[2][1])



    # Write object data.    
    def exportObject(self,file,obj,tracks):
        
        # Object datablock types
        BX_DATABLOCK_OBJECT     = 1
        BX_DATABLOCK_MESH       = 2
        BX_DATABLOCK_MATERIAL   = 3
        BX_DATABLOCK_TEXTURE    = 4
        BX_DATABLOCK_ARMATURE   = 5 
        BX_DATABLOCK_CAMERA     = 6
        BX_DATABLOCK_LAMP       = 7
        BX_DATABLOCK_CURVE      = 8    
        
        print("  Object : \"" + obj.name  +"\"")
        file.writeStr(obj.name)
        
        datablock_id = 0
        datablock_node = None
        
        # Mesh type
        if (obj.type=="MESH"):
            file.writeInt( BX_DATABLOCK_MESH )
            datablock_node = self.MeshCollection.find(obj.data.name)
            if not(datablock_node):
                print("   Error : Mesh datablock not found.")
                return False
            
        # Empty type
        elif (obj.type=="EMPTY"):
            file.writeInt( BX_DATABLOCK_OBJECT )

        # Lamp type    
        elif (obj.type=="LAMP"):
            file.writeInt( BX_DATABLOCK_LAMP )
            datablock_node = self.LampCollection.find(obj.data.name)
            if not(datablock_node):
                print("   Error : Lamp datablock not found.")
                return False
                        
        # Camera type        
        elif (obj.type=="CAMERA"):
            file.writeInt( BX_DATABLOCK_CAMERA )
            datablock_node = self.CameraCollection.find(obj.data.name)
            if not(datablock_node):
                print("   Error : Camera datablock not found.")
                return False
        
        # Curve type
        elif (obj.type=="CURVE"):
            file.writeInt( BX_DATABLOCK_CURVE )
            datablock_node = self.CurveCollection.find(obj.data.name)
            if not(datablock_node):
                print("   Error : Curve datablock not found.")
                return False            
        
        # Curve type
        elif (obj.type=="ARMATURE"):
            file.writeInt( BX_DATABLOCK_ARMATURE )
            datablock_node = self.ArmatureCollection.find(obj.data.name)
            if not(datablock_node):
                print("   Error : Armature datablock not found.")
                return False        

        if(datablock_node):
            file.writeInt(datablock_node.id)
            
        if(obj.parent!=None):
            no = self.ObjectCollection.find(obj.parent.name)
            if(no):
                file.writeInt(no.id+1)
            else:
                print("   Error : Parent object not found.")
                return False
        else:
            file.writeInt(0)
        
        obj_mat = obj.matrix_local
        
        if(obj.parent):
            obj_mat = Matrix(obj_mat * obj.matrix_parent_inverse)
        
        position = obj_mat.to_translation()
        file.writeVec3(position.x,position.y,position.z)
        
        rotation = obj_mat.to_quaternion()
        file.writeVec4(rotation.x,rotation.y,rotation.z,rotation.w)
        
        scale = obj_mat.to_scale()
        file.writeVec3(scale.x,scale.y,scale.z)
                
        # Animation graph
        self.exportObjectTracks(file,obj,tracks)
        
        return True
    
    def EulerToMatrix(self,vec):
        return Matrix.Rotation(vec.x,4,'X') * Matrix.Rotation(vec.y,4,'Y') * Matrix.Rotation(vec.z,4,'Z')
    
    def ScaleMatrix(self,vec):
        return Matrix([[vec.x,0,0,0],[0,vec.y,0,0],[0,0,vec.z,0],[0,0,0,1]])
    
    # Write object animation data.
    def exportObjectTracks(self,file,obj,tracks):  
        tmpTracks = [] 

        if tracks != None:
            for t in tracks:
                if not "armature" in t:
                    tmpTracks.append(t)
                
        file.writeInt(len(tmpTracks))
        print("   Tracks : "+str(len(tmpTracks))) 
        
        for t in tmpTracks:
            file.writeStr(t["name"])
            file.writeInt(len(t["strips"]))
            
            print("    Track : \""+t["name"]+"\"")
            print("    Strips : "+str(len(t["strips"])))    
             
            for s in t["strips"]:
                
                file.writeVec2(s["range"].x,s["range"].y)
                print("     Range : ["+ str(s["range"].x)+", "+str(s["range"].y)+"]")
                graphs = s["groups"].keys()
                
                # Don't use groups
                file.writeInt(0)
                
                # Get total number of graphs in the groups
                graphsCount = 0
                for gName in graphs:
                    gData = s["groups"][gName]
                    graphsCount += len(gData)   
                print("     Graphs: "+str(graphsCount))
                file.writeInt(graphsCount)
                
                for gName in graphs:
                    gData = s["groups"][gName]
                    print("      Type : "+gName)   
                    
                    axiscount = len(gData)
                    if(axiscount != 3):
                        print("Error, 3 axis required!")
                        return False
                    
                    if len(gData[0]) != len(gData[1]) or len(gData[1]) != len(gData[2]):
                        print("Error, different number of keyframes in axis")
                        return False

                    kfcount = len(gData[0])
                    print("      Keyframes : "+str(kfcount))
                                        
                    val_transform = [[],[],[]]
                    axis_codes = None
                    
                    mat_transform = Matrix()
                    if obj.parent_type == 'OBJECT':
                        mat_transform = obj.matrix_parent_inverse
                        
                    # Perform inverse transform ?
                    for i in range(kfcount):
                        kx = gData[0][i];
                        ky = gData[1][i];
                        kz = gData[2][i];
                        
                        time_left = kx[0].x
                        time_center = kx[1].x
                        time_right = kx[2].x
                        
                        val_left = Vector([kx[0].y,ky[0].y,kz[0].y])
                        val_center = Vector([kx[1].y,ky[1].y,kz[1].y])
                        val_right = Vector([kx[2].y,ky[2].y,kz[2].y])
                        
                        if gName == "position":
                            axis_codes = [BX_GRAPH_LOC_X,BX_GRAPH_LOC_Y,BX_GRAPH_LOC_Z]
                        elif gName == "euler":
                            axis_codes = [BX_GRAPH_ROT_X,BX_GRAPH_ROT_Y,BX_GRAPH_ROT_Z]
                        elif gName == "scale":
                            axis_codes = [BX_GRAPH_SCALE_X,BX_GRAPH_SCALE_Y,BX_GRAPH_SCALE_Z]
                        else:
                            print("Error, unknown graph group name")
                            return False
                        
                        """
                        print(val_left)
                        print(val_center)
                        print(val_right)
                        
                        if ktype == "position":
                            val_left = (Matrix.Translation(val_left) * mat_transform).to_translation()
                            val_center = (Matrix.Translation(val_center) * mat_transform).to_translation()
                            val_right = (Matrix.Translation(val_right) * mat_transform).to_translation()
                            print("position")
                        elif ktype == "euler":
                            val_left = (self.EulerToMatrix(val_left) * mat_transform).to_euler()
                            val_center = (self.EulerToMatrix(val_center) * mat_transform).to_euler()
                            val_right = (self.EulerToMatrix(val_right) * mat_transform).to_euler()
                        elif ktype == "scale":
                            val_left = (self.ScaleMatrix(val_left) * mat_transform).to_scale()
                            val_center = (self.ScaleMatrix(val_center) * mat_transform).to_scale()
                            val_right = (self.ScaleMatrix(val_right) * mat_transform).to_scale()
                        
                        print(val_left)
                        print(val_center)
                        print(val_right)
                        """
                                               
                        val_transform[0].append([[time_left,val_left.x],[time_center,val_center.x],[time_right,val_right.x]])
                        val_transform[1].append([[time_left,val_left.y],[time_center,val_center.y],[time_right,val_right.y]])
                        val_transform[2].append([[time_left,val_left.z],[time_center,val_center.z],[time_right,val_right.z]])
                    
                    # Write animation data to file
                    for iaxis in range(axiscount):
                        file.writeInt(axis_codes[iaxis]) # graph type
                        file.writeInt(len(val_transform[iaxis])) # number of keyframes
                        for ikeyframe in range(kfcount):
                            v = val_transform[iaxis][ikeyframe]
                            file.writeFloat(v[0][0])
                            file.writeFloat(v[0][1])
                            file.writeFloat(v[1][0])
                            file.writeFloat(v[1][1])
                            file.writeFloat(v[2][0])
                            file.writeFloat(v[2][1])
                            
                    
    ## Write mesh data. 
    def exportMesh(self,file,mesh,users):
        print("  Mesh : \"" + mesh.name  +"\"")
        
        textureGroups = len(mesh.uv_textures)
        colorGroups = len(mesh.vertex_colors)
        
        file.writeStr(mesh.name)

        file.writeInt(len(mesh.vertices))
        file.writeInt(len(mesh.polygons))    
        file.writeInt(len(mesh.materials))    
        file.writeInt(textureGroups)
        file.writeInt(0) # vertex groups

        file.writeBool(colorGroups>0)
    
        print("   Vertices : " + str(len(mesh.vertices)))
        print("   Faces : " + str(len(mesh.polygons)))
        print("   Materials : " + str(len(mesh.materials)))
        print("   UV layers : " + str(textureGroups))
        print("   Colors : " + str(colorGroups>0))
        file.writeInt(0) # shapekeys
        
        # Write materials names.
        if mesh.materials:
            for m in mesh.materials:
                mat = self.MaterialCollection.find(m.name)
                if(mat==None):
                    #print("   Error : Material not found!")
                    #return False
                    file.writeInt(-1)
                else:
                    file.writeInt(mat.id)
                    
        if mesh.uv_textures:
            for m in mesh.uv_textures:
                file.writeStr(m.name)
        
        for vt in mesh.vertices:
            file.writeVec3(vt.co.x,vt.co.y,vt.co.z)
            file.writeVec3(vt.normal.x,vt.normal.y,vt.normal.z)
            file.writeInt(0)
        
        for i,fc in enumerate(mesh.polygons):
            file.writeInt(len(fc.vertices))
            file.writeInt(fc.material_index)
            
            for k,v in enumerate(fc.vertices):
                file.writeInt(v)
                
                for j in range(textureGroups):
                    file.writeVec2(mesh.uv_layers[j].data[fc.loop_indices[k]].uv[0],mesh.uv_layers[j].data[fc.loop_indices[k]].uv[1])
                    
                if(colorGroups>0):
                    c = mesh.vertex_colors[0].data[fc.loop_indices[k]].color;
                    file.writeCol4ub((int)(c[0]*255),(int)(c[1]*255),(int)(c[2]*255),255)
        
        return True

    ## Write bXporter file from selected elements.    
    def export(self,file):
        
        BX_VERSION = 202
        
        obj_vector = self.ObjectCollection.getNonSortedVector()
        mesh_vector = self.MeshCollection.getNonSortedVector()
        material_vector = self.MaterialCollection.getNonSortedVector()
        texture_vector = self.TextureCollection.getNonSortedVector()
        armature_vector = self.ArmatureCollection.getNonSortedVector()
        lamp_vector = self.LampCollection.getNonSortedVector()
        camera_vector = self.CameraCollection.getNonSortedVector()    
        curve_vector = self.CurveCollection.getNonSortedVector()    
            
        file.writeStr("BXDATA")
        file.writeInt(BX_VERSION)
        
        file.writeInt(self.TextureCollection.size())                
        file.writeInt(self.MaterialCollection.size())                    
        file.writeInt(self.MeshCollection.size())
        file.writeInt(self.CameraCollection.size())    
        file.writeInt(self.ArmatureCollection.size())
        file.writeInt(self.CurveCollection.size())
        file.writeInt(self.LampCollection.size())                            
        file.writeInt(self.ObjectCollection.size())
        
        if(texture_vector!=None):
            for t in texture_vector:
                if not(self.exportTexture(file,t[1].data)):
                    return False
                
        if(material_vector!=None):
            for m in material_vector:
                if not(self.exportMaterial(file,m[1].data)):
                    return False
                                                    
        if(mesh_vector!=None):
            for m in mesh_vector:
                if not(self.exportMesh(file,m[1].data,m[1].users)):
                    return False
                                
        if(camera_vector!=None):
            for c in camera_vector:
                if not(self.exportCamera(file,c[1].data)):
                    return False
                
        if(armature_vector!=None):
            for a in armature_vector:
                ue = []
                for u in a[1].users:
                    ue.append(self.ObjectCollection.find(u.name))
                if not(self.exportArmature(file,a[1].data,ue)):
                    return False                    

        if(curve_vector!=None):
            for a in curve_vector:
                if not(self.exportCurve(file,a[1].data)):
                    return False    
                    
        if(lamp_vector!=None):
            for a in lamp_vector:
                if not(self.exportLamp(file,a[1].data)):
                    return False    
                                                
                                                
        if(obj_vector!=None):
            for o in obj_vector:
                if not(self.exportObject(file,o[1].data,o[1].tracks)):
                    return False

#******************************************************************************#

def runExport(filepath):
    start = time.clock()
    filepath = bpy.path.ensure_ext(filepath, ".bx")
    
    print("bXporter start")

    fx = bXBinaryFileWriter()
    fx.open(filepath)

    bx = bXporter()
    bx.getSelected()
    bx.export(fx)

    fx.close()
    
    if(bpy.context.scene.bx_run_optimizer):
        outputfile = bpy.path.ensure_ext(filepath,".nc")
        optimizer_filename = bpy.context.scene.bx_optimizer_filename;
        print(" Starting optimizer...")
        print("  Optimizer: \""+ optimizer_filename+"\"")
        print("  Input: \"" + filepath+"\"");
        print("  Output: \"" + outputfile+"\"")
        res = subprocess.Popen([optimizer_filename, '-i', filepath,'-o',outputfile],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        res.wait()
        #print(res.stdout.read())
        os.remove(filepath)
    
    print("bXporter done @ "+time.ctime()+" in " +str(round(time.clock() - start,4))+"s\n")

    
#******************************************************************************#

class bXporterPanel(bpy.types.Panel):
    bl_space_type = "PROPERTIES" 
    bl_region_type = "WINDOW"
    bl_label = "bXporter"
    bl_context = "render"
    def draw(self, context):
        self.layout.prop(bpy.context.scene, "bx_export_filename")
        self.layout.prop(bpy.context.scene, "bx_optimizer_filename")
        self.layout.prop(bpy.context.scene, "bx_run_optimizer")
        self.layout.operator("bxporter.do_export")

class OBJECT_OT_ExportButton(bpy.types.Operator):
    bl_idname = "bxporter.do_export"
    bl_label = "Export"
 
    def execute(self, context):
        bpy.context.scene.bx_export_filename = bpy.context.scene.bx_export_filename.strip()
        if len(bpy.context.scene.bx_export_filename) > 0:
            runExport(bpy.context.scene.bx_export_filename)
        return{'FINISHED'}    


#******************************************************************************#

###### EXPORT OPERATOR #######
class Export_bx(bpy.types.Operator, ExportHelper):
    '''Exports selected objects as bXporter file'''
    bl_idname = "export_scene.bx"
    bl_label = "Export BX"
    filename_ext = ".bx"

    #optimize_flag = None

    @classmethod
    def poll(cls, context):
        return context.active_object.type in {'MESH','CAMERA','LAMP','EMPTY','ARMATURE','CURVE'}

    def execute(self, context):
        runExport(self.filepath)
        bpy.context.scene.bx_export_filename = self.filepath

        return {'FINISHED'}
    
    def invoke(self, context, event):
        wm = context.window_manager
        self.filepath = bpy.context.scene.bx_export_filename

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

### REGISTER ###

def menu_func(self, context):
    self.layout.operator(Export_bx.bl_idname, text="bXporter (.bx)")


def register():
    bpy.utils.register_module(__name__)
    bpy.types.INFO_MT_file_export.append(menu_func)

def unregister():
    bpy.utils.unregister_module(__name__)
    bpy.types.INFO_MT_file_export.remove(menu_func)

bpy.types.Scene.bx_export_filename = StringProperty(name="Export filename",default="",)
bpy.types.Scene.bx_run_optimizer = BoolProperty(name="Run optimizer",default=False,)
bpy.types.Scene.bx_optimizer_filename = StringProperty(name="Optimizer filename",default=bx_optimizer_default_filename,)

bpy.utils.register_class(bXporterPanel) 

if __name__ == "__main__":
    register()


#runExport("C:\\Projectos\\temp.bx")