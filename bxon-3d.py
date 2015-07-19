# ##### BEGIN ZLIB LICENSE BLOCK #####
#
# Copyright (c) 2015 Luis F.Loureiro
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
from bxon import *
import struct, time, sys, os, math, codecs
from bpy_extras.io_utils import ExportHelper
from bpy.props import *

## Blender dictionary object entry     
class bXMapEntry:
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

## Indexed Blender objects dictionary
class bXMap:
    # Dictionary atribute.
    dictionary = {}
    
    ## Constructor.
    def __init__(self):
        self.dictionary = {}
    
    ## Add a element to the dictionary.
    def add(self, data, key = None):
        d_e = bXMapEntry(data,len(self.dictionary))
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

## Objects animation tracks enumeration
def bXListAnimationData(obj):
    tracks = []
    
    if obj.animation_data != None:
        if obj.animation_data.action != None:
            action = obj.animation_data.action
            range = action.frame_range
            name = action.name
            gr = bXListActionCurves(action)
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
                    gr = bXListActionCurves(action)
                    if "bones" in gr: aflag = True
                    tstrips.append({"range":range,"groups":gr})
                rtrack = {"name":name,"strips":tstrips}
                if aflag: rtrack["armature"] = True
                tracks.append(rtrack)
    return tracks

## Animation curves enumeration 
def bXListActionCurves(action):
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

class bXExporter:

    ## Constructor.
    def __init__(self):
        self.objectMap = bXMap()
        self.meshMap = bXMap()
        self.materialMap = bXMap()
        self.textureMap = bXMap()
        self.lampMap = bXMap()
        self.armatureMap = bXMap()
        self.cameraMap = bXMap()
        self.curveMap = bXMap()
    
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
                atracks = bXListAnimationData(o)
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
    def exportTexture(self, map, entry):
        tex = entry.data
        print("  Texture : \"" + tex.name + "\"")
        node = map.put(tex.name,bxon_map())
        node.put("type", "image")
        node.put("filename", os.path.basename(tex.image.filepath))
        return True

    ## Export texture mapping mode.
    def exportTextureMapping(self, map, slot):
        node = map.put(slot.name,bxon_map())
        
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
        else:
            print("   Error : Texture type isn't supported.")
            return False
        return True
        
    ## Write material data.
    def exportMaterial(self, map, entry):
        mat = entry.data
        print("  Material : \"" + mat.name + "\"")
        node = map.put(mat.name,bxon_map())
        
        diffuse = node.put("diffuse", bxon_array(nType=BXON_FLOAT, nCount = 1, nStride = 3))
        diffuse.push(mat.diffuse_color)
       
        node.put("alpha",mat.alpha)
        
        specular = node.put("specular", bxon_array(nType=BXON_FLOAT, nCount = 1, nStride = 3))
        specular.push(mat.specular_color)

        node.put("diffuse_intensity",mat.diffuse_intensity)
        node.put("specular_intensity",mat.specular_intensity)
        
        node.put("ambient",mat.ambient)

        if(mat.transparency_method == "Z_TRANSPARENCY"):
            node.put("transparency_method","alpha_blend")
    
        for tname in mat.texture_slots.keys():
            t = mat.texture_slots[tname]
            if(t.texture.type=="IMAGE"):
                 self.exportTextureMapping(node,t)   
        return True

    ## Write camera data.    
    def exportCamera(self, map, entry):
        cam = entry.data
        print("  Camera : \"" + cam.name + "\"")
        node = map.put(cam.name, bxon_map())
        node.put("fov",(180/math.pi)*2*math.atan(16/(cam.lens* 1.3254834)))
        node.put("start", cam.clip_start)
        node.put("end", cam.clip_end)
        return True
        
    ## Write lamp data.
    def exportLamp(self, map, entry):
        lamp = entry.data
        print("  Lamp : \"" + lamp.name + "\"")
        node = map.put(lamp.name, bxon_map())
        diffuse = node.put("color", bxon_array(nType=BXON_FLOAT, nCount = 1, nStride = 3))
        diffuse.push(lamp.color)
        node.put("energy", lamp.energy)
        node.put("distance", lamp.distance)                
        return True
        
    ## Write curve data.
    def exportCurve(self, pNode, curve):
        print("  Curve : \"" + curve.name + "\"")
        node = pNode.put(curve.name, bxon_map())
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
    
    ## Write armature data.
    def exportArmature(self, map, entry):
        arm = entry.data
        print("  Armature : \"" + arm.name + "\"")
        node = map.put(arm.name, bxon_map())
        
        bonesMap = bXMap()
            
        for b_k in arm.bones.keys():
            bonesMap.add(None,arm.bones[b_k])
        
        bones = node.put("bones", bxon_map())
        
        for b_k in arm.bones.keys():
            b = arm.bones[b_k]
            
            bp_head = Vector()
            bp_tail = Vector()
            
            bNode = bones.put(b.name,bxon_map())
            
            bp_node = None    
            if(b.parent):
                bp_node = bonesMap.find(b.parent.name)
                
            if(bp_node):
                bp_head = bp_node.data.head_local
                bp_tail = bp_node.data.tail_local
                bNode.put("parent", b.parent.name)
                          
            head = b.head_local-bp_tail
            tail = b.tail_local-bp_tail
            
            head = bNode.put("head", bxon_array(nType = BXON_FLOAT, nCount = 1, nStride = 3))
            head.push(head)

            tail = bNode.put("tail", bxon_array(nType=BXON_FLOAT, nCount = 1, nStride = 3))
            tail.push(tail)
            
        return True
        
    # Write object data.    
    def exportObject(self, map, entry):
        obj = entry.data
        print("  Object : \"" + obj.name + "\"")
        node = map.put(obj.name, bxon_map())
      
        datablock_type = None
        datablock_id = None
        
        if (obj.type == "MESH"):
            datablock_type = "mesh"
            datablock_id = obj.data.name
            
        elif (obj.type == "EMPTY"):
            datablock_type = "empty"
        elif (obj.type == "LAMP"):
            datablock_type = "lamp"
            datablock_id = obj.data.name
            
        elif (obj.type == "CAMERA"):
            datablock_type = "camera"
            datablock_id = obj.data.name
            
        elif (obj.type == "CURVE"):
            datablock_type = "curve"
            datablock_id = obj.data.name
                     
        elif (obj.type == "ARMATURE"):
            datablock_type = "armature"
            datablock_id = obj.data.name
                  

        datablock = node.put("datablock", bxon_map())
        datablock.put("type", datablock_type)
        
        if(datablock_id):
            datablock.put("id", datablock_id)
        
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
        rotation.push(obj_mat.to_quaternion())
        
        scale = node.put("scale", bxon_array(nType=BXON_FLOAT, nCount = 1, nStride = 3))
        scale.push(obj_mat.to_scale())
        
        return True
            
    def exportMesh(self, map, entry):
        obj = entry.users[0]
        mesh = entry.data;
        
        print("  Mesh : \"" + obj.name + "\"")
        mesh = obj.data
        
        node = map.put(mesh.name,bxon_map())

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
            map = pNode.put("texture", bxon_map())
            for t in texture_vector:
                if not(self.exportTexture(map, t)):
                    print("   Error")
                    return False
                
        if(material_vector != None):
            map = pNode.put("material", bxon_map())
            for m in material_vector:
                if not(self.exportMaterial(map, m)):
                    print("   Error")
                    return False
                                                    
        if(mesh_vector != None):
            map = pNode.put("mesh", bxon_map())
            for m in mesh_vector:
                if not(self.exportMesh(map, m)):
                    print("   Error")
                    return False
                                
        if(camera_vector != None):
            map = pNode.put("camera", bxon_map())
            for c in camera_vector:
                if not(self.exportCamera(map, c)):
                    print("   Error")
                    return False
                
        if(armature_vector != None):
            map = pNode.put("armature", bxon_map())
            for a in armature_vector:
                #ue = []
                #for u in a[1].users:
                #    ue.append(self.objectMap.find(u.name))
                if not(self.exportArmature(map,a)):
                    return False                    

        if(curve_vector != None):
            map = pNode.put("curve", bxon_map())
            for a in curve_vector:
                if not(self.exportCurve(map, a)):
                    return False    
                    
        if(lamp_vector != None):
            map = pNode.put("lamp", bxon_map())
            for a in lamp_vector:
                if not(self.exportLamp(map, a)):
                    return False    
                                          
        if(obj_vector != None):
            map = pNode.put("object", bxon_map())
            for o in obj_vector:
                if not(self.exportObject(map,o)):
                    return False

def runExport(filename):
    print("\nbxon-3d start, " + time.ctime())
    start_time = time.time()

    f = open(filename,"wb")
    ctx = bxon_context(f)

    root = bxon_map(ctx)

    bX = bXExporter()

    bX.getSelected()

    print("\n Exporting")
    bX.export(root)
    
    root.flush()
    f.close()

    elapsed_time = time.time() - start_time
    print("\n Time: " + str(math.floor(elapsed_time*1000)) + " ms")
    print("bxon-3d end")

###### EXPORT OPERATOR #######
class Export_bxon(bpy.types.Operator, ExportHelper):
    '''Exports selected objects as bxon-3d file'''
    bl_idname = "bxon_export"
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
    self.layout.operator(Export_bxon.bl_idname, text="bxon-3d (.bxon)")

def register():
    bpy.utils.register_module(__name__)
    bpy.types.INFO_MT_file_export.append(menu_func)

def unregister():
    bpy.utils.unregister_module(__name__)
    bpy.types.INFO_MT_file_export.remove(menu_func)

if __name__ == "__main__":
    #runExport("test.bxon")
    register()

