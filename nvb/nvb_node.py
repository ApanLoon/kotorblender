"""TODO: DOC."""
import re
import mathutils
import bpy
import bpy_extras.image_utils
import bmesh
from bpy_extras.io_utils import unpack_list, unpack_face_list

from . import nvb_glob
from . import nvb_def
from . import nvb_utils
from . import nvb_aabb
from . import nvb_parse
from . import nvb_txi

class FaceList():
    def __init__(self):
        self.faces = []  # int 3-tuple, vertex indices
        self.shdgr = []  # int, shading group for this face
        self.uvIdx = []  # int 3-tuple, texture/uv vertex indices
        self.matId = []  # int, material index


class FlareList():
    def __init__(self):
        self.textures    = []
        self.sizes       = []
        self.positions   = []
        self.colorshifts = []


class GeometryNode():
    """
    Basic node from which every other is derived
    """
    def __init__(self, name = 'UNNAMED'):
        self.nodetype = 'undefined'

        self.roottype = 'mdl'
        self.rootname = 'undefined'

        self.name        = name
        self.parentName  = nvb_def.null
        self.position    = (0.0, 0.0, 0.0)
        self.orientation = (0.0, 0.0, 0.0, 0.0)
        self.scale       = 1.0
        self.wirecolor   = (0.0, 0.0, 0.0)

        # Name of the corresponding object in blender
        # (used to resolve naming conflicts)
        self.objref   = ''
        # Parsed lines (by number), allow last parser to include unhandled data
        self.parsed_lines = [];
        self.rawascii         = '' # unprocessed directives



    def __eq__(self, other):
        if isinstance(other, Base):
            return self.name == other.name


    def __ne__(self, other):
        return not self.__eq__(self, other)


    def __str__(self):
        return 'node ' + self.nodetype + ' ' + self.name


    def parse1f(self, asciiBlock, floatList):
        l_float = float
        for line in asciiBlock:
            floatList.append(l_float(line[0]))


    def parse2f(self, asciiBlock, floatList):
        l_float = float
        for line in asciiBlock:
            floatList.append( (l_float(line[0]), l_float(line[1])) )


    def parse3f(self, asciiBlock, floatList):
        l_float = float
        for line in asciiBlock:
            floatList.append( (l_float(line[0]), l_float(line[1]), l_float(line[2])) )


    def loadAscii(self, asciiNode):
        l_float = float
        l_isNumber = nvb_utils.isNumber

        for index, line in enumerate(asciiNode):
            try:
                label = line[0].lower()
            except IndexError:
                # Probably empty line or whatever, skip it
                continue

            if not l_isNumber(label):
                if (label == 'node'):
                    self.name = nvb_utils.getName(line[2])
                    self.parsed_lines.append(index)
                elif (label == 'endnode'):
                    self.parsed_lines.append(index)
                    return
                elif (label == 'parent'):
                    self.parentName = nvb_utils.getName(line[1])
                    self.parsed_lines.append(index)
                elif (label == 'position'):
                    self.position = (l_float(line[1]),
                                     l_float(line[2]),
                                     l_float(line[3]))
                    self.parsed_lines.append(index)
                elif (label == 'orientation'):
                    self.orientation = (l_float(line[1]),
                                        l_float(line[2]),
                                        l_float(line[3]),
                                        l_float(line[4]))
                    self.parsed_lines.append(index)
                elif (label == 'scale'):
                    self.scale = l_float(line[1])
                    self.parsed_lines.append(index)
                elif (label == 'wirecolor'):
                    self.wirecolor = (l_float(line[1]),
                                      l_float(line[2]),
                                      l_float(line[3]))
                    self.parsed_lines.append(index)

    def setObjectData(self, obj):
        self.objref = obj.name  # used to resolve naming conflicts
        nvb_utils.setObjectRotationAurora(obj, self.orientation)
        obj.scale         = (self.scale, self.scale, self.scale)
        obj.location      = self.position
        obj.nvb.wirecolor = self.wirecolor
        # add unprocessed data as text objects
        if (len(self.rawascii)):
            txt = bpy.data.texts.new(obj.name)
            txt.write(self.rawascii)
            obj.nvb.rawascii = txt.name


    def addToScene(self, scene):
        obj = bpy.data.objects.new(self.name, None)
        self.setObjectData(obj)
        scene.objects.link(obj)
        return obj

    def getAdjustedMatrix(self, obj):

        if obj.parent:
            parent_mw = obj.parent.matrix_world
        else:
            parent_mw = mathutils.matrix()

        p_mw_scale = parent_mw.to_scale()

        # scale_m = mathutils.Matrix([[p_mw_scale[0],0,0,0],
        #                             [0,p_mw_scale[1],0,0],
        #                             [0,0,p_mw_scale[2],0],
        #                             [0,0,0            ,1]])

        scaled = obj.matrix_local.copy()
        scaled[0][3] = scaled[0][3] * p_mw_scale[0]
        scaled[1][3] = scaled[1][3] * p_mw_scale[1]
        scaled[2][3] = scaled[2][3] * p_mw_scale[2]
        return scaled

    def addDataToAscii(self, obj, asciiLines, classification = nvb_def.Classification.UNKNOWN, simple = False, nameDict = None):
        if obj.parent and nameDict and obj.parent.name in nameDict:
            asciiLines.append('  parent ' + nameDict[obj.parent.name])
        elif obj.parent:
            asciiLines.append('  parent ' + obj.parent.name)
        else:
            asciiLines.append('  parent ' + nvb_def.null)
        # Scaling fix
        transmat = self.getAdjustedMatrix(obj)
        loc = transmat.to_translation()
        s = '  position {: .7g} {: .7g} {: .7g}'.format(round(loc[0], 7), round(loc[1], 7), round(loc[2], 7))
        asciiLines.append(s)

        #rot = nvb_utils.euler2nwangle(transmat.to_euler('XYZ'))
        rot = nvb_utils.getAuroraRotFromObject(obj)
        s = '  orientation {: .7g} {: .7g} {: .7g} {: .7g}'.format(round(rot[0], 7), round(rot[1], 7), round(rot[2], 7), round(rot[3], 7))
        asciiLines.append(s)
        '''
        loc = obj.location
        s = '  position {: .7g} {: .7g} {: .7g}'.format(round(loc[0], 7), round(loc[1], 7), round(loc[2], 7))
        asciiLines.append(s)

        rot = nvb_utils.getAuroraRotFromObject(obj)
        s = '  orientation {: .7g} {: .7g} {: .7g} {: .7g}'.format(round(rot[0], 7), round(rot[1], 7), round(rot[2], 7), round(rot[3], 7))
        asciiLines.append(s)
        '''
        color = obj.nvb.wirecolor
        asciiLines.append('  wirecolor ' + str(round(color[0], 2)) + ' ' +
                                           str(round(color[1], 2)) + ' ' +
                                           str(round(color[2], 2)) )
        scale = round(nvb_utils.getAuroraScale(obj), 3)
        if (scale != 1.0):
            asciiLines.append('  scale ' + str(scale))

        # Write out the unprocessed data
        if obj.nvb.rawascii and obj.nvb.rawascii in bpy.data.texts:
            asciiLines.append('  ' + '\n  '.join(bpy.data.texts[obj.nvb.rawascii].as_string().strip().split('\n')))

    def toAscii(self, obj, asciiLines, classification = nvb_def.Classification.UNKNOWN, simple = False, nameDict = None):
        if nameDict and obj.name in nameDict:
            asciiLines.append('node ' + self.nodetype + ' ' + nameDict[obj.name])
        else:
            asciiLines.append('node ' + self.nodetype + ' ' + obj.name)
        self.addDataToAscii(obj, asciiLines, classification, simple, nameDict=nameDict)
        asciiLines.append('endnode')

    def addUnparsedToRaw(self, asciiNode):
        for idx, line in enumerate(asciiNode):
            if idx in self.parsed_lines or not len(''.join(line).strip()):
                continue
            self.rawascii += '\n' + ' '.join(line)


class Dummy(GeometryNode):
    '''

    '''
    def __init__(self, name = 'UNNAMED'):
        GeometryNode.__init__(self, name)
        self.nodetype  = 'dummy'

        self.dummytype = nvb_def.Dummytype.NONE

    def loadAscii(self, asciiNode):
        GeometryNode.loadAscii(self, asciiNode)

    def setObjectData(self, obj):
        GeometryNode.setObjectData(self, obj)

        obj.nvb.dummytype = self.dummytype

        obj.nvb.dummysubtype = nvb_def.DummySubtype.NONE
        subtypes = nvb_def.DummySubtype.SUFFIX_LIST
        for element in subtypes:
            if self.name.endswith(element[0]):
                obj.nvb.dummysubtype = element[1]
                break

    def addDataToAscii(self, obj, asciiLines, classification = nvb_def.Classification.UNKNOWN, simple = False, nameDict=None):
        if obj.parent and nameDict and obj.parent.name in nameDict:
            asciiLines.append('  parent ' + nameDict[obj.parent.name])
        elif obj.parent:
            asciiLines.append('  parent ' + obj.parent.name)
        else:
            asciiLines.append('  parent ' + nvb_def.null)

        dummytype = obj.nvb.dummytype
        if dummytype == nvb_def.Dummytype.MDLROOT:
            # Only parent for rootdummys
            return

        # scale = round(nvb_utils.getAuroraScale(obj), 3)
        # Scaling fix
        asciiLines.append('  scale 1.0')
        '''
        if (scale != 1.0):
            asciiLines.append('  scale ' + str(scale))
        '''

        # Scaling fix
        transmat = self.getAdjustedMatrix(obj)
        loc = transmat.to_translation()
        s = '  position {: .7g} {: .7g} {: .7g}'.format(round(loc[0], 7), round(loc[1], 7), round(loc[2], 7))
        asciiLines.append(s)

        rot = nvb_utils.euler2nwangle(transmat.to_euler('XYZ'))
        s = '  orientation {: .7g} {: .7g} {: .7g} {: .7g}'.format(round(rot[0], 7), round(rot[1], 7), round(rot[2], 7), round(rot[3], 7))
        asciiLines.append(s)
        '''
        loc = obj.location
        s = '  position {: .7g} {: .7g} {: .7g}'.format(round(loc[0], 7), round(loc[1], 7), round(loc[2], 7))
        asciiLines.append(s)

        rot = nvb_utils.getAuroraRotFromObject(obj)
        s = '  orientation {: .7g} {: .7g} {: .7g} {: .7g}'.format(round(rot[0], 7), round(rot[1], 7), round(rot[2], 7), round(rot[3], 7))
        asciiLines.append(s)
        '''

        color = obj.nvb.wirecolor
        asciiLines.append('  wirecolor ' + str(round(color[0], 2)) + ' ' +
                                           str(round(color[1], 2)) + ' ' +
                                           str(round(color[2], 2)) )

        # TODO: Handle types and subtypes, i.e. Check and modify name
        subtype = obj.nvb.dummysubtype
        if subtype == nvb_def.Dummytype.NONE:
            pass


class Patch(GeometryNode):
    """Same as a plain Dummy."""

    def __init__(self, name = 'UNNAMED'):
        GeometryNode.__init__(self, name)
        self.nodetype = 'patch'

        self.dummytype = nvb_def.Dummytype.PATCH

    def setObjectData(self, obj):
        GeometryNode.setObjectData(self, obj)

        obj.nvb.dummytype = self.dummytype


class Reference(GeometryNode):
    """Contains a reference to another mdl."""

    def __init__(self, name = 'UNNAMED'):
        GeometryNode.__init__(self, name)
        self.nodetype = 'reference'

        self.dummytype = nvb_def.Dummytype.REFERENCE
        self.refmodel     = nvb_def.null
        self.reattachable = 0

    def loadAscii(self, asciiNode):
        GeometryNode.loadAscii(self, asciiNode)
        l_isNumber = nvb_utils.isNumber

        for idx, line in enumerate(asciiNode):
            try:
                label = line[0].lower()
            except IndexError:
                # Probably empty line or whatever, skip it
                continue
            if not l_isNumber(label):
                if (label == 'refmodel'):
                    # self.refmodel = line[1].lower()
                    self.refmodel = line[1]
                    self.parsed_lines.append(idx)
                elif (label == 'reattachable'):
                    self.reattachable = int(line[1])
                    self.parsed_lines.append(idx)
        if (self.nodetype == 'reference'):
            self.addUnparsedToRaw(asciiNode)


    def setObjectData(self, obj):
        GeometryNode.setObjectData(self, obj)
        obj.nvb.dummytype    = self.dummytype
        obj.nvb.refmodel     = self.refmodel
        obj.nvb.reattachable = (self.reattachable == 1)


    def addDataToAscii(self, obj, asciiLines, classification = nvb_def.Classification.UNKNOWN, simple = False, nameDict=None):
        GeometryNode.addDataToAscii(self, obj, asciiLines, classification, nameDict=nameDict)
        asciiLines.append('  refmodel ' + obj.nvb.refmodel)
        asciiLines.append('  reattachable ' + str(int(obj.nvb.reattachable)))


class Trimesh(GeometryNode):
    """TODO: Doc."""

    def __init__(self, name = 'UNNAMED'):
        GeometryNode.__init__(self, name)
        self.nodetype = 'trimesh'

        self.meshtype         = nvb_def.Meshtype.TRIMESH
        self.center           = (0.0, 0.0, 0.0) # Unused ?
        self.lightmapped      = 0
        self.render           = 1
        self.shadow           = 1
        self.beaming          = 0
        self.inheritcolor     = 0  # Unused ?
        self.m_bIsBackgroundGeometry = 0
        self.dirt_enabled     = 0
        self.dirt_texture     = 1
        self.dirt_worldspace  = 1
        self.hologram_donotdraw = 0
        self.animateuv        = 0
        self.uvdirectionx     = 1.0
        self.uvdirectiony     = 1.0
        self.uvjitter         = 0.0
        self.uvjitterspeed    = 0.0
        self.alpha            = 1.0
        self.transparencyhint = 0
        self.selfillumcolor   = (0.0, 0.0, 0.0)
        self.ambient          = (0.0, 0.0, 0.0)
        self.diffuse          = (0.0, 0.0, 0.0)
        self.bitmap           = nvb_def.null
        self.bitmap2          = nvb_def.null
        self.tangentspace     = 0
        self.rotatetexture    = 0
        self.verts            = [] # list of vertices
        self.facelist         = FaceList()
        self.tverts           = [] # list of texture vertices
        self.tverts1          = [] # list of texture vertices
        self.texindices1      = [] # list of texture vertex indices
        self.roomlinks        = [] # walkmesh only
        self.lytposition      = (0.0, 0.0, 0.0)

    def createImage(self, imgName, imgPath):
        image = bpy_extras.image_utils.load_image(imgName + '.tga',
                                                  imgPath,
                                                  recursive=nvb_glob.textureSearch,
                                                  place_holder=False,
                                                  ncase_cmp=True)
        if (image is None):
            print('Kotorblender - WARNING: Could not load image ' + imgName)
            print(imgPath)
            image = bpy.data.images.new(imgName, 512, 512)
        else:
            image.name = imgName

        return image

    def loadAscii(self, asciiNode):
        GeometryNode.loadAscii(self, asciiNode)

        l_int   = int
        l_float = float
        l_isNumber = nvb_utils.isNumber
        for idx, line in enumerate(asciiNode):
            try:
                label = line[0].lower()
            except IndexError:
                # Probably empty line or whatever, skip it
                continue

            if not l_isNumber(label):
                if (label == 'render'):
                    self.render = l_int(line[1])
                    self.parsed_lines.append(idx)
                elif (label == 'shadow'):
                    self.shadow = l_int(line[1])
                    self.parsed_lines.append(idx)
                elif (label == 'lightmapped'):
                    self.lightmapped = l_int(line[1])
                    self.parsed_lines.append(idx)
                elif (label == 'beaming'):
                    self.beaming = l_int(line[1])
                    self.parsed_lines.append(idx)
                elif (label == 'inheritcolor '):
                    self.inheritcolor = l_int(line[1])
                    self.parsed_lines.append(idx)
                elif (label == 'tangentspace'):
                    self.tangentspace = l_int(line[1])
                    self.parsed_lines.append(idx)
                elif (label == 'rotatetexture'):
                    self.rotatetexture = l_int(line[1])
                    self.parsed_lines.append(idx)
                elif (label == 'm_bisbackgroundgeometry'):
                    self.m_bIsBackgroundGeometry = l_int(line[1])
                    self.parsed_lines.append(idx)
                elif (label == 'dirt_enabled'):
                    self.dirt_enabled = l_int(line[1])
                    self.parsed_lines.append(idx)
                elif (label == 'dirt_texture'):
                    self.dirt_texture = l_int(line[1])
                    self.parsed_lines.append(idx)
                elif (label == 'dirt_worldspace'):
                    self.dirt_worldspace = l_int(line[1])
                    self.parsed_lines.append(idx)
                elif (label == 'hologram_donotdraw'):
                    self.hologram_donotdraw = l_int(line[1])
                    self.parsed_lines.append(idx)
                elif (label == 'animateuv'):
                    self.animateuv = l_int(line[1])
                    self.parsed_lines.append(idx)
                elif (label == 'uvdirectionx'):
                    self.uvdirectionx = l_float(line[1])
                    self.parsed_lines.append(idx)
                elif (label == 'uvdirectiony'):
                    self.uvdirectiony = l_float(line[1])
                    self.parsed_lines.append(idx)
                elif (label == 'uvjitter'):
                    self.uvjitter = l_float(line[1])
                    self.parsed_lines.append(idx)
                elif (label == 'uvjitterspeed'):
                    self.uvjitterspeed = l_float(line[1])
                    self.parsed_lines.append(idx)
                elif (label == 'alpha'):
                    self.alpha = l_float(line[1])
                    self.parsed_lines.append(idx)
                elif (label == 'transparencyhint'):
                    self.transparencyhint = l_int(line[1])
                    self.parsed_lines.append(idx)
                elif (label == 'selfillumcolor'):  # Self illumination color
                    self.selfillumcolor = (l_float(line[1]),
                                           l_float(line[2]),
                                           l_float(line[3]))
                    self.parsed_lines.append(idx)
                elif (label == 'ambient'):
                    self.ambient = (l_float(line[1]),
                                    l_float(line[2]),
                                    l_float(line[3]))
                    self.parsed_lines.append(idx)
                elif (label == 'diffuse'):
                    self.diffuse = (l_float(line[1]),
                                    l_float(line[2]),
                                    l_float(line[3]))
                    self.parsed_lines.append(idx)
                elif (label == 'center'):
                    # Unused ? Becuase we don't do anything with this
                    try:
                        self.center = (l_float(line[1]),
                                       l_float(line[2]),
                                       l_float(line[3]))
                        self.parsed_lines.append(idx)
                    except:
                        # Probably an 'undefined' string which cannot be
                        # converted to float
                        pass
                elif (label == 'bitmap'):
                    self.bitmap = line[1]
                    self.parsed_lines.append(idx)
                elif (label == 'bitmap2'):
                    self.bitmap2 = line[1]
                    self.parsed_lines.append(idx)
                elif (label == 'verts'):
                    numVals = l_int(line[1])
                    nvb_parse.f3(asciiNode[idx+1:idx+numVals+1], self.verts)
                    #self.verts = [(float(l[0]), float(l[1]), float(l[2])) for l in asciiNode[idx+1:idx+numVals+1]]
                    self.parsed_lines.extend(range(idx,idx+numVals+1))
                elif (label == 'faces'):
                    numVals = l_int(line[1])
                    self.parseFaceList(asciiNode[idx+1:idx+numVals+1])
                    self.parsed_lines.extend(range(idx,idx+numVals+1))
                elif (label == 'tverts'):
                    numVals = l_int(line[1])
                    nvb_parse.f2(asciiNode[idx+1:idx+numVals+1], self.tverts)
                    #self.tverts = [(float(l[0]), float(l[1])) for l in asciiNode[idx+1:idx+numVals+1]]
                    self.parsed_lines.extend(range(idx,idx+numVals+1))
                elif (label == 'tverts1'):
                    numVals = l_int(line[1])
                    nvb_parse.f2(asciiNode[idx+1:idx+numVals+1], self.tverts1)
                    self.parsed_lines.extend(range(idx,idx+numVals+1))
                elif (label == 'texindices1'):
                    numVals = l_int(line[1])
                    nvb_parse.i3(asciiNode[idx+1:idx+numVals+1], self.texindices1, initialFloat=False)
                    self.parsed_lines.extend(range(idx,idx+numVals+1))
                elif (label == 'roomlinks'):
                    try:
                        numVals = l_int(line[1])
                    except:
                        numVals = next((i for i, v in enumerate(asciiNode[idx+1:]) if not l_isNumber(v[0])), -1)
                    nvb_parse.i2(asciiNode[idx+1:idx+numVals+1], self.roomlinks)
                    self.parsed_lines.extend(range(idx,idx+numVals+1))
        if (self.nodetype == 'trimesh'):
            self.addUnparsedToRaw(asciiNode)


    def parseFaceList(self, asciiFaces):
        l_int = int
        for line in asciiFaces:
            self.facelist.faces.append((l_int(line[0]),
                                        l_int(line[1]),
                                        l_int(line[2])))
            self.facelist.shdgr.append(l_int(line[3]))
            self.facelist.uvIdx.append((l_int(line[4]),
                                        l_int(line[5]),
                                        l_int(line[6])))
            self.facelist.matId.append(l_int(line[7]))

    def createMaterial(self, name, bitmap):
        material = None
        texName  = self.bitmap.lower()
        if nvb_glob.materialMode == 'SIN':
            # Avoid duplicate materials, search for similar ones.
            material = nvb_utils.materialExists(self.diffuse,
                                                (0.0, 0.0, 0.0),
                                                texName,
                                                self.alpha)

        if not material:
            material = bpy.data.materials.new(name)
            material.diffuse_color     = self.diffuse
            material.diffuse_intensity = 1.0

            if not nvb_utils.isNull(self.bitmap):
                textureSlot = material.texture_slots.add()
                # If a texture with the same name was already created treat
                # them as if they were the same, i.e. just use the old one
                if (texName in bpy.data.textures):
                    textureSlot.texture = bpy.data.textures[texName]
                else:
                    textureSlot.texture = bpy.data.textures.new(texName, type='IMAGE')
                textureSlot.texture_coords        = 'UV'
                textureSlot.use_map_color_diffuse = True

                # Load the image for the texture, but check if it was
                # already loaded before. If so, use that one.
                imgName = bitmap
                if (imgName in bpy.data.images):
                    image = bpy.data.images[imgName]
                    textureSlot.texture.image = image
                else:
                    image = self.createImage(imgName, nvb_glob.texturePath)
                    if image is not None:
                        textureSlot.texture.image = image
                if self.tangentspace == 1:
                    textureSlot.texture.nvb.bumpmapped = True
                nvb_txi.loadTxi(textureSlot.texture)

            nvb_utils.setMaterialAuroraAlpha(material, self.alpha)

        return material


    def createMesh(self, name):
        # Create the mesh itself
        mesh = bpy.data.meshes.new(name)
        mesh.vertices.add(len(self.verts))
        mesh.vertices.foreach_set('co', unpack_list(self.verts))
        mesh.tessfaces.add(len(self.facelist.faces))
        mesh.tessfaces.foreach_set('vertices_raw', unpack_face_list(self.facelist.faces))

        # Special handling for converted sabermesh
        if name.startswith('2081__'):
            mesh.show_double_sided = True

        # Special handling for mesh in walkmesh files
        if self.roottype in ['pwk', 'dwk', 'wok']:
            # Create walkmesh materials
            for wokMat in nvb_def.wok_materials:
                matName = wokMat[0]
                # Walkmesh materials will be shared across multiple walkmesh
                # objects
                if matName in bpy.data.materials:
                    material = bpy.data.materials[matName]
                else:
                    material = bpy.data.materials.new(matName)
                    material.diffuse_color      = wokMat[1]
                    material.diffuse_intensity  = 1.0
                    material.specular_color     = (0.0,0.0,0.0)
                    material.specular_intensity = wokMat[2]
                mesh.materials.append(material)

            # Apply the walkmesh materials to each face
            for idx, face in enumerate(mesh.tessfaces):
                face.material_index = self.facelist.matId[idx]

        # Create material
        if nvb_glob.materialMode != 'NON' and self.roottype == 'mdl':
            material = self.createMaterial(name, self.bitmap)
            mesh.materials.append(material)

            # Lightmap material?
            if (not nvb_utils.isNull(self.bitmap2)):
                # configure material:
                material.use_shadeless = True
                texName = self.bitmap2.lower()
                textureSlot = material.texture_slots.add()
                # If a texture with the same name was already created treat
                # them as if they were the same, i.e. just use the old one
                if (texName in bpy.data.textures):
                    textureSlot.texture = bpy.data.textures[texName]
                else:
                    textureSlot.texture = bpy.data.textures.new(texName, type='IMAGE')
                textureSlot.texture_coords        = 'UV'
                textureSlot.use_map_color_diffuse = True
                textureSlot.blend_type            = 'OVERLAY'
                # set slot 0's uv layer now

                # Load the image for the texture, but check if it was
                # already loaded before. If so, use that one.
                imgName = self.bitmap2
                if (imgName in bpy.data.images):
                    image = bpy.data.images[imgName]
                    textureSlot.texture.image = image
                else:
                    image = self.createImage(imgName, nvb_glob.texturePath)
                    if image is not None:
                        textureSlot.texture.image = image

            # Create UV map
            if (len(self.tverts) > 0) and (mesh.tessfaces):
                uv = mesh.tessface_uv_textures.new(name + '.uv')
                mesh.tessface_uv_textures.active = uv

                for i in range(len(self.facelist.uvIdx)):
                    # Get a tessface
                    tessface = mesh.tessfaces[i]
                    # Apply material (there is only ever one)
                    tessface.material_index = 0
                    # Grab a uv for the face
                    tessfaceUV = mesh.tessface_uv_textures[0].data[i]
                    # Get the indices of the 3 uv's for this face
                    uvIdx = self.facelist.uvIdx[i]

                    # BEGIN EEEKADOODLE FIX
                    # BUG: Evil eekadoodle problem where faces that have
                    # vert index 0 at location 3 are shuffled.
                    vertIdx = self.facelist.faces[i]
                    if vertIdx[2] == 0:
                        uvIdx = uvIdx[1], uvIdx[2], uvIdx[0]
                    # END EEEKADOODLE FIX

                    # Add uv coordinates to face
                    tessfaceUV.uv1 = self.tverts[uvIdx[0]]
                    tessfaceUV.uv2 = self.tverts[uvIdx[1]]
                    tessfaceUV.uv3 = self.tverts[uvIdx[2]]

                    # Apply texture to uv face
                    if (not nvb_utils.isNull(self.bitmap)) and material.texture_slots[0]:
                        tessfaceUV.image = material.texture_slots[0].texture.image

            # Create lightmap UV map
            if (len(self.tverts1) > 0) and (mesh.tessfaces):
                lm_idx = len(mesh.tessface_uv_textures)
                uv = mesh.tessface_uv_textures.new(name + '_lm.uv')
                #mesh.tessface_uv_textures.active = uv

                for i in range(len(self.facelist.uvIdx)):
                    # Get a tessface
                    tessface = mesh.tessfaces[i]
                    # Apply material (there is only ever one)
                    tessface.material_index = 0
                    # Grab a uv for the face
                    tessfaceUV = mesh.tessface_uv_textures[lm_idx].data[i]
                    # Get the indices of the 3 uv's for this face
                    uvIdx = self.facelist.uvIdx[i]
                    if len(self.texindices1) and i < len(self.texindices1):
                        uvIdx = self.texindices1[i]

                    # BEGIN EEEKADOODLE FIX
                    # BUG: Evil eekadoodle problem where faces that have
                    # vert index 0 at location 3 are shuffled.
                    vertIdx = self.facelist.faces[i]
                    if vertIdx[2] == 0:
                        uvIdx = uvIdx[1], uvIdx[2], uvIdx[0]
                    # END EEEKADOODLE FIX

                    # Add uv coordinates to face
                    tessfaceUV.uv1 = self.tverts1[uvIdx[0]]
                    tessfaceUV.uv2 = self.tverts1[uvIdx[1]]
                    tessfaceUV.uv3 = self.tverts1[uvIdx[2]]

                    # Apply texture to uv face
                    if (not nvb_utils.isNull(self.bitmap2)) and material.texture_slots[1]:
                        tessfaceUV.image = material.texture_slots[1].texture.image
                if material.texture_slots[1]:
                    material.texture_slots[1].uv_layer = name + '_lm.uv'
                if material.texture_slots[0]:
                    material.texture_slots[0].uv_layer = name + '.uv'

        # Import smooth groups as sharp edges
        if nvb_glob.importSmoothGroups:
            bm = bmesh.new()
            mesh.update()
            bm.from_mesh(mesh)
            if hasattr(bm.edges, "ensure_lookup_table"):
                bm.edges.ensure_lookup_table()
            # Mark edge as sharp if its faces belong to different smooth groups
            for e in bm.edges:
                f = e.link_faces
                #if (len(f) > 1) and (self.facelist.shdgr[f[0].index] != self.facelist.shdgr[f[1].index]):
                if (len(f) > 1) and not (self.facelist.shdgr[f[0].index] & self.facelist.shdgr[f[1].index]):
                    edgeIdx = e.index
                    mesh.edges[edgeIdx].use_edge_sharp = True
            bm.free()
            del bm
            mesh.show_edge_sharp = True
            mesh.update()
            # load all smoothgroup numbers into a mesh data layer per-poly
            mesh_sg_list = mesh.polygon_layers_int.new(nvb_def.sg_layer_name)
            #print("sg list {} shdgr {}".format(len(mesh_sg_list.data), len(self.facelist.shdgr)))
            mesh_sg_list.data.foreach_set('value', self.facelist.shdgr)

        if self.roottype == 'wok' and len(self.roomlinks):
            self.setRoomLinks(mesh)

        mesh.update()
        return mesh

    def setRoomLinks(self, mesh):
        #if len(self.roomlinks) < 1:
        #    return
        if not 'RoomLinks' in mesh.vertex_colors:
            room_vert_colors = mesh.vertex_colors.new('RoomLinks')
        else:
            room_vert_colors = mesh.vertex_colors['RoomLinks']
        for link in self.roomlinks:
            # edge indices don't really match up, but face order does
            faceIdx = int(link[0] / 3)
            edgeIdx = link[0] % 3
            room_color = [ 0.0 / 255, (200 + link[1]) / 255.0, 0.0 / 255 ]
            realIdx = 0
            for face_idx, face in enumerate(mesh.polygons):
            #for idx in range(0, faceIdx - 1):
                #if mesh.polygons[faceIdx].material_index == 7:
                #if face.material_index != 7:
                if face.material_index not in nvb_def.WkmMaterial.NONWALKABLE:
                    if realIdx == faceIdx:
                        faceIdx = face_idx
                        break
                    else:
                        realIdx += 1
            face = mesh.polygons[faceIdx]
            print(face.edge_keys)
            for vert_idx, loop_idx in zip(face.vertices, face.loop_indices):
                #if vert_idx in mesh.edges[link[0]].vertices:
                if vert_idx in face.edge_keys[edgeIdx]:
                    room_vert_colors.data[loop_idx].color = room_color

    def getRoomLinks(self, mesh):
        """Construct list of room links from vertex colors, for wok files"""
        if not 'RoomLinks' in mesh.vertex_colors:
            return
        room_vert_colors = mesh.vertex_colors['RoomLinks']
        #roomlinks = []
        self.roomlinks = []
        face_bonus = 0
        for face_idx, face in enumerate(mesh.polygons):
            verts = {}
            # when the wok is compiled, these faces will be sorted past
            # the walkable faces, so take the index delta into account
            if self.nodetype != 'aabb' and face.material_index in nvb_def.WkmMaterial.NONWALKABLE:
                face_bonus -= 1
                continue
            for vert_idx, loop_idx in zip(face.vertices, face.loop_indices):
                room = int(round(room_vert_colors.data[loop_idx].color[1] * 255, 0)) - 200
                #room = int(room_vert_colors.data[loop_idx].color[1] * 255) - 200
                #print('room {:}'.format(room))
                #print('color {:.7g}'.format(room_vert_colors.data[loop_idx].color[1]))
                # we use color space for links to 55 rooms,
                # which is likely more than the game could handle
                if room < 0 or room > 54:
                    continue
                verts[vert_idx] = room
                #print(room)
            if len(verts) < 2:
                continue
            vertIndices = list(verts.keys())
            for edge_idx, edge in enumerate(face.edge_keys):
                #print(vertIndices)
                #print(edge)
                if vertIndices[0] in edge and vertIndices[1] in edge:
                    #roomlinks.append(((face_idx + face_bonus) * 3 + edge_idx, room))
                    self.roomlinks.append(((face_idx + face_bonus) * 3 + edge_idx, verts[vertIndices[0]]))

    def setObjectData(self, obj):
        GeometryNode.setObjectData(self, obj)

        obj.nvb.meshtype         = self.meshtype
        obj.nvb.lightmapped      = (self.lightmapped == 1)
        obj.nvb.render           = (self.render == 1)
        obj.nvb.shadow           = (self.shadow == 1)
        obj.nvb.beaming          = (self.beaming == 1)
        obj.nvb.inheritcolor     = (self.inheritcolor == 1)
        obj.nvb.rotatetexture    = (self.rotatetexture == 1)
        obj.nvb.m_bIsBackgroundGeometry = (self.m_bIsBackgroundGeometry == 1)
        obj.nvb.dirt_enabled     = (self.dirt_enabled == 1)
        obj.nvb.dirt_texture     = self.dirt_texture
        obj.nvb.dirt_worldspace  = self.dirt_worldspace
        obj.nvb.hologram_donotdraw = (self.hologram_donotdraw == 1)
        obj.nvb.animateuv        = (self.animateuv == 1)
        obj.nvb.uvdirectionx     = self.uvdirectionx
        obj.nvb.uvdirectiony     = self.uvdirectiony
        obj.nvb.uvjitter         = self.uvjitter
        obj.nvb.uvjitterspeed    = self.uvjitterspeed
        obj.nvb.transparencyhint = self.transparencyhint
        obj.nvb.selfillumcolor   = self.selfillumcolor
        obj.nvb.ambientcolor     = self.ambient
        obj.nvb.lytposition      = self.lytposition


    def addToScene(self, scene):
        if nvb_glob.minimapMode and not self.render:
            # Fading objects won't be imported in minimap mode
            # We may need it for the tree stucture, so import it as an empty
            return Dummy.addToScene(self, scene)
        mesh = self.createMesh(self.name)
        obj  = bpy.data.objects.new(self.name, mesh)
        self.setObjectData(obj)
        scene.objects.link(obj)
        return obj


    def addMaterialDataToAscii(self, obj, asciiLines):
        # Check if this object has a material assigned to it
        material = obj.active_material
        if material:
            color = material.diffuse_color
            asciiLines.append('  diffuse ' +    str(round(color[0], 2)) + ' ' +
                                                str(round(color[1], 2)) + ' ' +
                                                str(round(color[2], 2))  )

            # Check if this material has a texture assigned
            texture = material.active_texture
            imgName = nvb_def.null
            if texture:
                # Only image textures will be exported
                if (texture.type == 'IMAGE') and (texture.image):
                    imgName = nvb_utils.getImageFilename(texture.image)
                    if nvb_glob.exportTxi and not texture.nvb.exported_in_save:
                        nvb_txi.saveTxi(texture)
                        # set this to prevent multiple export of TXI in mdl save
                        texture.nvb.exported_in_save = True
                else:
                    imgName = nvb_def.null
                asciiLines.append('  tangentspace ' + str(int(texture.nvb.bumpmapped)))
            asciiLines.append('  bitmap ' + imgName)
            asciiLines.append('  alpha ' + str(round(nvb_utils.getAuroraAlpha(obj), 2)))
            # Test for lightmap assigned as second texture
            if material.texture_slots[1]:
                texture  = material.texture_slots[1].texture
                imgName = nvb_def.null
                if obj.nvb.lightmapped and texture and (texture.type == 'IMAGE') and (texture.image):
                    imgName = nvb_utils.getImageFilename(texture.image)
                # Write bitmap2 NULL if texture is removed/non-image or lightmapped was clicked off.
                # this is for when a model that imported with lightmapping is being exported without it,
                # possibly w/o disabling everything properly
                asciiLines.append('  bitmap2 ' + imgName)

        else:
            # No material, set some default values
            asciiLines.append('  diffuse 1.0 1.0 1.0')
            asciiLines.append('  alpha 1.0')
            asciiLines.append('  bitmap ' + nvb_def.null)
            asciiLines.append('  tangentspace 0')


    def addUVToList(self, uv, uvList, vert, vertList):
        """Helper function to keep UVs unique."""
        if uv in uvList and vert in vertList:
            return uvList.index(uv)
        else:
            uvList.append(uv)
            vertList.append(vert)
            return (len(uvList)-1)


    def addMeshDataToAscii(self, obj, asciiLines, simple = False):
        mesh = obj.to_mesh(nvb_glob.scene, nvb_glob.applyModifiers, nvb_glob.meshConvert)
        for p in mesh.polygons:
            p.use_smooth = True

        # Scaling fix
        # TODO: Find out how exactly blender handles scaling, which matrices to use etc
        scale = obj.matrix_world.to_scale()
        scale_matrix = mathutils.Matrix([[scale[0],0,0,0],
                                         [0,scale[1],0,0],
                                         [0,0,scale[2],0],
                                         [0,0,0       ,1]])
        # So... I could figure this out, but I need to know what breaks without this
        #mesh.transform(scale_matrix)

        # Triangulation (doing it with bmesh to retain edges marked as sharp)
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        bm.to_mesh(mesh)
        bm.free()
        del bm

        # Recalculate tessfaces for export
        mesh.calc_tessface()

        # Calculate smooth groups
        smoothGroups    = []
        numSmoothGroups = 0
        if (obj.nvb.smoothgroup == 'SEPR') or (not nvb_glob.exportSmoothGroups):
            # 0 = Do not use smoothgroups
            smoothGroups    = [0] * len(mesh.polygons)
            numSmoothGroups = 1
        elif (obj.nvb.smoothgroup == 'SING'):
            # All faces belong to smooth group 1
            smoothGroups    = [1] * len(mesh.polygons)
            numSmoothGroups = 1
        else:
            (smoothGroups, numSmoothGroups) = mesh.calc_smooth_groups(use_bitflags=True)
            #(smoothGroups, numSmoothGroups) = mesh.calc_smooth_groups(use_bitflags=False)

        faceList = [] # List of triangle faces
        uvList   = [] # List of uv indices
        uvVertList = [] # Temp list of uv verts used for each geometry vert
        # separate lists for the lightmap UVs if they exist
        uvListLM     = [] # List of uv indices
        uvVertListLM = [] # Temp list of uv verts used for each geometry vert

        abs_pos = (0.0, 0.0, 0.0)
        if self.roottype == 'wok' and obj.nvb.lytposition:
            abs_pos = (obj.nvb.lytposition[0] + obj.location[0],
                       obj.nvb.lytposition[1] + obj.location[1],
                       obj.nvb.lytposition[2] + obj.location[2])
        # Add vertices
        asciiLines.append('  verts ' + str(len(mesh.vertices)))
        l_round = round
        formatString = '    {: .7g} {: .7g} {: .7g}'
        for v in mesh.vertices:
            s = formatString.format(l_round(v.co[0] + abs_pos[0], 7),
                                    l_round(v.co[1] + abs_pos[1], 7),
                                    l_round(v.co[2] + abs_pos[2], 7))
            asciiLines.append(s)

        # Add faces and corresponding tverts and shading groups
        tessfaces     = mesh.tessfaces
        tessfaces_uvs = mesh.tessface_uv_textures.active
        tessfaces_uvs_lm = False
        smgroups_layer = mesh.polygon_layers_int.get(nvb_def.sg_layer_name)
        if len(mesh.tessface_uv_textures) > 1:
            tessfaces_uvs_lm = mesh.tessface_uv_textures[1]
        for idx in range(len(tessfaces)):
            tface   = tessfaces[idx]
            smGroup = smoothGroups[idx]
            if obj.nvb.smoothgroup == 'DRCT' and \
               smgroups_layer is not None and \
               smgroups_layer.data[idx].value != 0:
                smGroup = smgroups_layer.data[idx].value
            matIdx  = tface.material_index

            # We triangulated, so faces are always triangles
            uv1 = 0
            uv2 = 0
            uv3 = 0
            if tessfaces_uvs:
                uvData = tessfaces_uvs.data[idx]
                uv1 = self.addUVToList(uvData.uv1, uvList, tface.vertices[0], uvVertList)
                uv2 = self.addUVToList(uvData.uv2, uvList, tface.vertices[1], uvVertList)
                uv3 = self.addUVToList(uvData.uv3, uvList, tface.vertices[2], uvVertList)
            # constructing lightmap (second texture) UV list
            uv1LM = 0
            uv2LM = 0
            uv3LM = 0
            if tessfaces_uvs_lm:
                uvData = tessfaces_uvs_lm.data[idx]
                uv1LM = self.addUVToList(uvData.uv1, uvListLM, tface.vertices[0], uvVertListLM)
                uv2LM = self.addUVToList(uvData.uv2, uvListLM, tface.vertices[1], uvVertListLM)
                uv3LM = self.addUVToList(uvData.uv3, uvListLM, tface.vertices[2], uvVertListLM)

            faceList.append([tface.vertices[0], tface.vertices[1], tface.vertices[2], smGroup,
                             uv1, uv2, uv3, matIdx, uv1LM, uv2LM, uv3LM])

        # Check a texture, we don't want uv's when there is no texture
        material = obj.active_material
        texture  = None
        if material:
            texture = material.active_texture

        if simple or len(uvList) < 1:
            asciiLines.append('  faces ' + str(len(faceList)))

            vertDigits        = str(len(str(len(mesh.vertices))))
            smoothGroupDigits = str(len(str(numSmoothGroups)))
            formatString = '    {:' + vertDigits + 'd} {:' + vertDigits + 'd} {:' + vertDigits + 'd}  ' + \
                               '{:' + smoothGroupDigits + 'd}  ' + \
                               '0 0 0  ' + \
                               '{:2d}'
            for f in faceList:
                s = formatString.format(f[0], f[1], f[2], f[3], f[7])
                asciiLines.append(s)
        else:
            asciiLines.append('  faces ' + str(len(faceList)))

            vertDigits        = str(len(str(len(mesh.vertices))))
            smoothGroupDigits = str(len(str(numSmoothGroups)))
            uvDigits          = str(len(str(len(uvList))))
            formatString = '    {:' + vertDigits + 'd} {:' + vertDigits + 'd} {:' + vertDigits + 'd}  ' + \
                               '{:' + smoothGroupDigits + 'd}  ' + \
                               '{:' + uvDigits + 'd} {:' + uvDigits + 'd} {:' + uvDigits + 'd}  ' + \
                               '{:2d}'
            for f in faceList:
                s = formatString.format(f[0], f[1], f[2], f[3], f[4], f[5], f[6], f[7])
                asciiLines.append(s)

            if (len(uvList) > 0):
                asciiLines.append('  tverts ' + str(len(uvList)))
                formatString = '    {: .7g} {: .7g}'
                for uv in uvList:
                    s = formatString.format(round(uv[0], 7), round(uv[1], 7))
                    asciiLines.append(s)

            if (len(uvListLM) > 0):
                asciiLines.append('  tverts1 ' + str(len(uvListLM)))
                formatString = '    {: .7g} {: .7g} 0'
                for uv in uvListLM:
                    s = formatString.format(round(uv[0], 7), round(uv[1], 7))
                    asciiLines.append(s)
                asciiLines.append('  texindices1 ' + str(len(faceList)))
                formatString = '    {:3d} {:3d} {:3d}'
                for f in faceList:
                    asciiLines.append(formatString.format(f[8], f[9], f[10]))

            if len(mesh.vertex_colors.keys()) and \
               ('RoomLinks' not in mesh.vertex_colors or len(mesh.vertex_colors.keys()) > 1):
                # get dict key for first vertex color layer that is not RoomLinks
                colorKey = [k for k in mesh.vertex_colors.keys() if k != 'RoomLinks'][0]
                # insert the vertex colors
                asciiLines.append('  colors ' + str(len(mesh.vertices)))
                formatString = '    {: .7g} {: .7g} {: .7g}'
                for face in mesh.polygons:
                    for loop_idx in face.loop_indices:
                        print('loop ' + str(loop_idx) + '\n')
                        s = formatString.format(mesh.vertex_colors[colorKey].data[loop_idx].color[0],
                                                mesh.vertex_colors[colorKey].data[loop_idx].color[1],
                                                mesh.vertex_colors[colorKey].data[loop_idx].color[2])
                        asciiLines.append(s)
                # insert vertex color indices
                asciiLines.append('  colorindices ' + str(len(faceList)))
                for f in faceList:
                    s = formatString.format(f[0], f[1], f[2])
                    asciiLines.append(s)

        if self.roottype == 'wok' or self.nodetype == 'aabb':
            if self.nodetype == 'aabb':
                self.getRoomLinks(mesh)
            if len(self.roomlinks):
                asciiLines.append('  roomlinks ' + str(len(self.roomlinks)))
                for link in self.roomlinks:
                    asciiLines.append('    {:d} {:d}'.format(link[0], link[1]))

        bpy.data.meshes.remove(mesh)


    def addDataToAscii(self, obj, asciiLines, classification = nvb_def.Classification.UNKNOWN, simple = False, nameDict=None):
        GeometryNode.addDataToAscii(self, obj, asciiLines, classification, simple, nameDict=nameDict)

        color = obj.nvb.ambientcolor
        asciiLines.append('  ambient ' +    str(round(color[0], 2)) + ' ' +
                                            str(round(color[1], 2)) + ' ' +
                                            str(round(color[2], 2))  )
        self.addMaterialDataToAscii(obj, asciiLines)
        if not simple:


            color = obj.nvb.selfillumcolor
            asciiLines.append('  selfillumcolor ' + str(round(color[0], 2)) + ' ' +
                                                    str(round(color[1], 2)) + ' ' +
                                                    str(round(color[2], 2))  )

            asciiLines.append('  render ' + str(int(obj.nvb.render)))
            asciiLines.append('  shadow ' + str(int(obj.nvb.shadow)))
            asciiLines.append('  lightmapped ' + str(int(obj.nvb.lightmapped)))
            asciiLines.append('  beaming ' + str(int(obj.nvb.beaming)))
            asciiLines.append('  inheritcolor ' + str(int(obj.nvb.inheritcolor)))
            asciiLines.append('  m_bIsBackgroundGeometry ' + str(int(obj.nvb.m_bIsBackgroundGeometry)))
            asciiLines.append('  dirt_enabled ' + str(int(obj.nvb.dirt_enabled)))
            asciiLines.append('  dirt_texture ' + str(obj.nvb.dirt_texture))
            asciiLines.append('  dirt_worldspace ' + str(obj.nvb.dirt_worldspace))
            asciiLines.append('  hologram_donotdraw ' + str(int(obj.nvb.hologram_donotdraw)))
            asciiLines.append('  animateuv ' + str(int(obj.nvb.animateuv)))
            asciiLines.append('  uvdirectionx ' + str(obj.nvb.uvdirectionx))
            asciiLines.append('  uvdirectiony ' + str(obj.nvb.uvdirectiony))
            asciiLines.append('  uvjitter ' + str(obj.nvb.uvjitter))
            asciiLines.append('  uvjitterspeed ' + str(obj.nvb.uvjitterspeed))
            asciiLines.append('  transparencyhint ' + str(obj.nvb.transparencyhint))
            # These two are for tiles only
            if classification == 'TILE':
                asciiLines.append('  rotatetexture ' + str(int(obj.nvb.rotatetexture)))

        self.addMeshDataToAscii(obj, asciiLines, simple)


class Danglymesh(Trimesh):
    """

    """
    def __init__(self, name = 'UNNAMED'):
        Trimesh.__init__(self, name)
        self.nodetype = 'danglymesh'

        self.meshtype     = nvb_def.Meshtype.DANGLYMESH
        self.period       = 1.0
        self.tightness    = 1.0
        self.displacement = 1.0
        self.constraints  = []


    def loadAscii(self, asciiNode):
        Trimesh.loadAscii(self, asciiNode)

        l_int   = int
        l_float = float
        l_isNumber = nvb_utils.isNumber
        for idx, line in enumerate(asciiNode):
            try:
                label = line[0].lower()
            except IndexError:
                # Probably empty line or whatever, skip it
                continue

            if not l_isNumber(label):
                if   (label == 'period'):
                    self.period = l_float(line[1])
                    self.parsed_lines.append(idx)
                elif (label == 'tightness'):
                    self.tightness = l_float(line[1])
                    self.parsed_lines.append(idx)
                elif (label == 'displacement'):
                    self.displacement = l_float(line[1])
                    self.parsed_lines.append(idx)
                elif (label == 'constraints'):
                    numVals = l_int(line[1])
                    nvb_parse.f1(asciiNode[idx+1:idx+numVals+1], self.constraints)
                    #self.constraints = [float(l[0]) for l in asciiNode[idx+1:idx+numVals+1]]
                    self.parsed_lines.extend(range(idx,idx+numVals+1))
        if (self.nodetype == 'danglymesh'):
            self.addUnparsedToRaw(asciiNode)

    def addConstraintsToObject(self, obj):
        '''
        Creates a vertex group for the object to contain the vertex
        weights for the danglymesh. The weights are called "constraints"
        in NWN. Range is [0.0, 255.0] as opposed to [0.0, 1.0] in Blender
        '''
        vgroup = obj.vertex_groups.new('constraints')
        for vertexIdx, constraint in enumerate(self.constraints):
            weight = constraint/255
            vgroup.add([vertexIdx], weight, 'REPLACE')
        obj.nvb.constraints = vgroup.name


    def setObjectData(self, obj):
        Trimesh.setObjectData(self, obj)

        obj.nvb.period       = self.period
        obj.nvb.tightness    = self.tightness
        obj.nvb.displacement = self.displacement
        self.addConstraintsToObject(obj)


    def addConstraintsToAscii(self, obj, asciiLines):
        vgroupName = obj.nvb.constraints
        vgroup     = obj.vertex_groups[vgroupName]

        numVerts = len(obj.data.vertices)
        asciiLines.append('  constraints ' + str(numVerts))
        for i, v in enumerate(obj.data.vertices):
            try:
                asciiLines.append('    ' + str(round(vgroup.weight(i)*255, 3)))
            except:
                # Vertex is not part of this group
                asciiLines.append('    0.0')


    def addDataToAscii(self, obj, asciiLines, classification = nvb_def.Classification.UNKNOWN, simple = False, nameDict=None):
        Trimesh.addDataToAscii(self, obj, asciiLines, classification, nameDict=nameDict)

        asciiLines.append('  period '       + str(round(obj.nvb.period, 3)))
        asciiLines.append('  tightness '    + str(round(obj.nvb.tightness, 3)))
        asciiLines.append('  displacement ' + str(round(obj.nvb.displacement, 3)))
        self.addConstraintsToAscii(obj, asciiLines)


class Lightsaber(Trimesh):
    """

    """
    def __init__(self, name = 'UNNAMED'):
        Trimesh.__init__(self, name)
        self.nodetype = 'lightsaber'

        self.meshtype     = nvb_def.Meshtype.LIGHTSABER

    def createMesh(self, name):
            # Create the mesh itself
            mesh = Trimesh.createMesh(self, name)
            mesh.show_double_sided = True
            return mesh


class Skinmesh(Trimesh):
    """Skinmeshes are Trimeshes where every vertex has a weight."""

    def __init__(self, name = 'UNNAMED'):
        Trimesh.__init__(self, name)
        self.nodetype = 'skin'

        self.meshtype = nvb_def.Meshtype.SKIN
        self.weights = []

    def loadAscii(self, asciiNode):
        Trimesh.loadAscii(self, asciiNode)
        l_int      = int
        l_isNumber = nvb_utils.isNumber
        for idx, line in enumerate(asciiNode):
            try:
                label = line[0].lower()
            except IndexError:
                # Probably empty line or whatever, skip it
                continue

            if not l_isNumber(label):
                if (label == 'weights'):
                    numVals = l_int(line[1])
                    self.getWeightsFromAscii(asciiNode[idx+1:idx+numVals+1])
                    self.parsed_lines.extend(range(idx,idx+numVals+1))
                    break  # Only one value here, abort loop when read
        if (self.nodetype == 'skin'):
            self.addUnparsedToRaw(asciiNode)


    def getWeightsFromAscii(self, asciiBlock):
        lfloat = float
        lchunker = nvb_utils.chunker
        for line in asciiBlock:
            # A line looks like this
            # [group_name, vertex_weight, group_name, vertex_weight]
            # We create a list looking like this:
            # [[group_name, vertex_weight], [group_name, vertex_weight]]
            memberships = []
            for chunk in lchunker(line, 2):
                memberships.append([chunk[0], lfloat(chunk[1])])

            self.weights.append(memberships)


    def addSkinGroupsToObject(self, obj):
        skinGroupDict = {}
        for vertIdx, vertMemberships in enumerate(self.weights):
            for membership in vertMemberships:
                if membership[0] in skinGroupDict:
                    skinGroupDict[membership[0]].add([vertIdx], membership[1], 'REPLACE')
                else:
                    vgroup = obj.vertex_groups.new(membership[0])
                    skinGroupDict[membership[0]] = vgroup
                    vgroup.add([vertIdx], membership[1], 'REPLACE')

    def setObjectData(self, obj):
        Trimesh.setObjectData(self, obj)

        self.addSkinGroupsToObject(obj)

    def addWeightsToAscii(self, obj, asciiLines):
        # Get a list of skingroups for this object:
        # A vertex group is a skingroup if there is an object in the mdl
        # with the same name as the group
        skingroups = []
        for group in obj.vertex_groups:
            if nvb_utils.searchNodeInModel(
                obj,
                lambda o, test_name=group.name:
                    o.name == test_name or \
                    re.match(r'{}\.\d\d\d'.format(test_name), o.name)):
                skingroups.append(group)

        vertexWeights = []
        for i, v in enumerate(obj.data.vertices):
            weights = []
            for group in skingroups:
                try:
                    weights.append([group.name, group.weight(i)])
                except:
                    # Vertex not part of this group
                    pass
            vertexWeights.append(weights)

        numVerts = len(obj.data.vertices)
        asciiLines.append('  weights ' + str(numVerts))
        for weights in vertexWeights:
            line = '  '
            if weights:
                for w in weights:
                    line += '  ' + w[0] + ' ' + str(round(w[1], 3))
            else:
                # No weights for this vertex ... this is a problem
                print('Kotorblender - WARNING: Missing vertex weight in ' + obj.name)
                line = 'ERROR: no weight'
            asciiLines.append(line)


    def addDataToAscii(self, obj, asciiLines, classification = nvb_def.Classification.UNKNOWN, simple = False, nameDict=None):
        Trimesh.addDataToAscii(self, obj, asciiLines, classification, nameDict=nameDict)

        self.addWeightsToAscii(obj, asciiLines)


class Emitter(GeometryNode):
    emitter_attrs = [
        "deadspace",
        "blastradius",
        "blastlength",
        "numBranches",
        "controlptsmoothing",
        "xgrid",
        "ygrid",
        "spawntype",
        "update",
        "render",
        "blend",
        "texture",
        "chunkName",
        "twosidedtex",
        "loop",
        "renderorder",
        "m_bFrameBlending",
        "m_sDepthTextureName",
        "p2p",
        "p2p_sel",
        "affectedByWind",
        "m_isTinted",
        "bounce",
        "random",
        "inherit",
        "inheritvel",
        "inherit_local",
        "splat",
        "inherit_part",
        "depth_texture",
        "alphastart",
        "alphamid",
        "alphaend",
        "birthrate",
        "m_frandombirthrate",
        "bounce_co",
        "combinetime",
        "drag",
        "fps",
        "frameend",
        "framestart",
        "grav",
        "lifeexp",
        "mass",
        "p2p_bezier2",
        "p2p_bezier3",
        "particlerot",
        "randvel",
        "sizestart",
        "sizemid",
        "sizeend",
        "sizestart_y",
        "sizemid_y",
        "sizeend_y",
        "spread",
        "threshold",
        "velocity",
        "xsize",
        "ysize",
        "blurlength",
        "lightningdelay",
        "lightningradius",
        "lightningsubdiv",
        "lightningscale",
        "lightningzigzag",
        "percentstart",
        "percentmid",
        "percentend",
        "targetsize",
        "numcontrolpts",
        "controlptradius",
        "controlptdelay",
        "tangentspread",
        "tangentlength",
        "colorstart",
        "colormid",
        "colorend"]

    def __init__(self, name = 'UNNAMED'):
        GeometryNode.__init__(self, name)
        self.nodetype = 'emitter'

        self.meshtype = nvb_def.Meshtype.EMITTER
        # object data
        self.deadspace = 0.0
        self.blastradius = 0.0
        self.blastlength = 0.0
        self.numBranches = 0
        self.controlptsmoothing = 0
        self.xgrid = 0
        self.ygrid = 0
        self.spawntype = ''
        self.update = ''
        self.render = ''
        self.blend = ''
        self.texture = ''
        self.chunkName = ''
        self.twosidedtex = False
        self.loop = False
        self.renderorder = 0
        self.m_bFrameBlending = False
        self.m_sDepthTextureName = nvb_def.null
        # flags
        self.p2p = False
        self.p2p_sel = False
        self.affectedByWind = False
        self.m_isTinted = False
        self.bounce = False
        self.random = False
        self.inherit = False
        self.inheritvel = False
        self.inherit_local = False
        self.splat = False
        self.inherit_part = False
        self.depth_texture = False
        # controllers
        self.alphastart = 0.0
        self.alphamid = 0.0
        self.alphaend = 0.0
        self.birthrate = 0
        self.m_frandombirthrate = 0
        self.bounce_co = 0.0
        self.combinetime = 0.0
        self.drag = 0.0
        self.fps = 0
        self.frameend = 0
        self.framestart = 0
        self.grav = 0.0
        self.lifeexp = 0.0
        self.mass = 0.0
        self.p2p_bezier2 = 0.0
        self.p2p_bezier3 = 0.0
        self.particlerot = 0.0
        self.randvel = 0.0
        self.sizestart = 0.0
        self.sizemid = 0.0
        self.sizeend = 0.0
        self.sizestart_y = 0.0
        self.sizemid_y = 0.0
        self.sizeend_y = 0.0
        self.spread = 0.0
        self.threshold = 0.0
        self.velocity = 0.0
        self.xsize = 2
        self.ysize = 2
        self.blurlength = 0.0
        self.lightningdelay = 0.0
        self.lightningradius = 0.0
        self.lightningsubdiv = 0
        self.lightningscale = 0.0
        self.lightningzigzag = 0
        self.percentstart = 0.0
        self.percentmid = 0.0
        self.percentend = 0.0
        self.targetsize = 0
        self.numcontrolpts = 0
        self.controlptradius = 0.0
        self.controlptdelay = 0
        self.tangentspread = 0
        self.tangentlength = 0.0
        self.colorstart = (1.0, 1.0, 1.0)
        self.colormid = (1.0, 1.0, 1.0)
        self.colorend = (1.0, 1.0, 1.0)
        # unidentified stuff
        self.rawascii = ''


    def loadAscii(self, asciiNode):
        l_float = float
        l_isNumber = nvb_utils.isNumber

        for line in asciiNode:
            try:
                label = line[0].lower()
            except IndexError:
                # Probably empty line or whatever, skip it
                continue

            if not l_isNumber(label):
                if (label == 'node'):
                    self.name = nvb_utils.getName(line[2])
                elif (label == 'endnode'):
                    return
                elif (label == 'parent'):
                    self.parentName = nvb_utils.getName(line[1])
                elif (label == 'position'):
                    self.position = (l_float(line[1]),
                                     l_float(line[2]),
                                     l_float(line[3]))
                elif (label == 'orientation'):
                    self.orientation = (l_float(line[1]),
                                        l_float(line[2]),
                                        l_float(line[3]),
                                        l_float(line[4]))
                elif (label == 'scale'):
                    self.scale = l_float(line[1])
                elif (label == 'wirecolor'):
                    self.wirecolor = (l_float(line[1]),
                                      l_float(line[2]),
                                      l_float(line[3]))
                elif (label in list(map(lambda x: x.lower(), dir(self)))):
                    # this block covers all object data and controllers
                    attrname = [name for name in dir(self) if name.lower() == label][0]
                    default_value = getattr(self, attrname)
                    try:
                        if isinstance(default_value, str):
                            setattr(self, attrname, line[1])
                        elif isinstance(default_value, bool):
                            setattr(self, attrname, bool(int(line[1])))
                        elif isinstance(default_value, int):
                            setattr(self, attrname, int(line[1]))
                        elif isinstance(default_value, float):
                            setattr(self, attrname, float(line[1]))
                        elif isinstance(default_value, tuple):
                            setattr(self, attrname, tuple(map(float, line[1:])))
                    except:
                        continue
                else:
                    self.rawascii += '\n  ' + ' '.join(line)

    def createMesh(self, objName):
        # Create the mesh itself
        mesh = bpy.data.meshes.new(objName)
        mesh.vertices.add(4)
        mesh.vertices[0].co = ( (self.xsize/2) / 100.0,  (self.ysize/2) / 100.0, 0.0)
        mesh.vertices[1].co = ( (self.xsize/2) / 100.0, (-self.ysize/2) / 100.0, 0.0)
        mesh.vertices[2].co = ((-self.xsize/2) / 100.0, (-self.ysize/2) / 100.0, 0.0)
        mesh.vertices[3].co = ((-self.xsize/2) / 100.0,  (self.ysize/2) / 100.0, 0.0)
        mesh.tessfaces.add(1)
        mesh.tessfaces.foreach_set('vertices_raw', [0, 1, 2, 3])

        # After calling update() tessfaces become inaccessible
        mesh.validate()
        mesh.update()

        return mesh


    def addRawAscii(self, obj):
        txt = bpy.data.texts.new(obj.name)
        txt.write(self.rawascii)
        obj.nvb.rawascii = txt.name


    def setObjectData(self, obj):
        GeometryNode.setObjectData(self, obj)

        obj.nvb.meshtype = self.meshtype

        for attrname in self.emitter_attrs:
            value = getattr(self, attrname)
            # Enum translation is not pretty...
            if attrname == 'spawntype':
                if value == '0':
                    value = 'Normal'
                elif value == '1':
                    value = 'Trail'
                else:
                    value = 'NONE'
            elif attrname == 'update':
                if value.title() not in ['Fountain', 'Single', 'Explosion', 'Lightning']:
                    value = 'NONE'
                else:
                    value = value.title()
            elif attrname == 'render':
                attrname = 'render_emitter'
                if value not in ['Normal', 'Billboard_to_Local_Z', 'Billboard_to_World_Z',
                                 'Aligned_to_World_Z', 'Aligned_to_Particle_Dir', 'Motion_Blur']:
                    value = 'NONE'
            elif attrname == 'blend':
                if value.lower() == 'punchthrough':
                    value = 'Punch-Through'
                elif value.title() not in ['Lighten', 'Normal', 'Punch-Through']:
                    value = 'NONE'
            # translate p2p_sel to metaproperty p2p_type
            elif attrname == 'p2p_sel':
                if self.p2p_sel:
                    obj.nvb.p2p_type = 'Bezier'
                else:
                    obj.nvb.p2p_type = 'Gravity'
                # p2p_type has update method, sets p2p_sel
                # except it doesn't seem to initially
                obj.nvb.p2p_sel = self.p2p_sel
                continue
            #print(attrname)
            setattr(obj.nvb, attrname, value)

        #self.addRawAscii(obj)


    def addToScene(self, scene):
        if nvb_glob.minimapMode:
            # We don't need emitters in minimap mode
            # We may need it for the tree stucture, so import it as an empty
            return GeometryNode.addToScene(self, scene)

        mesh = self.createMesh(self.name)
        obj  = bpy.data.objects.new(self.name, mesh)

        self.setObjectData(obj)
        scene.objects.link(obj)
        return obj


    def addDataToAscii(self, obj, asciiLines, classification = nvb_def.Classification.UNKNOWN, simple = False, nameDict=None):
        GeometryNode.addDataToAscii(self, obj, asciiLines, classification, simple, nameDict=nameDict)

        # export the copious amounts of emitter data
        for attrname in self.emitter_attrs:
            if attrname == 'render':
                value = obj.nvb.render_emitter
            else:
                value = getattr(obj.nvb, attrname)
            if attrname == 'spawntype':
                if value == 'Normal':
                    value = 0
                elif value == 'Trail':
                    value = 1
            if isinstance(value, mathutils.Color):
                value = ' '.join(list(map(lambda x: '{:.6g}'.format(x), value)))
            elif isinstance(value, tuple):
                value = ' '.join(list(map(lambda x: '{:.6g}'.format(x), value)))
            elif isinstance(value, float):
                value = "{:.7g}".format(value)
            elif isinstance(value, bool):
                value = str(int(value))
            elif isinstance(value, str) and (not value or value == 'NONE'):
                continue
            else:
                value = str(value)
            asciiLines.append('  {} {}'.format(attrname, value))

        return
        # this is now handled by geometry node class...
        if obj.nvb.rawascii not in bpy.data.texts:
            print('Kotorblender - WARNING: No emitter data for ' + obj.name)
            return
        txt      = bpy.data.texts[obj.nvb.rawascii]
        txtLines = [l.split() for l in txt.as_string().split('\n')]
        for line in txtLines:
            try:
                label = line[0].lower()
            except IndexError:
                # Probably empty line or whatever, skip it
                continue
            if (label == 'node') or (label  == 'endnode') or \
               (label == 'parent') or (label == 'position') or \
               (label == 'orientation') or (label == 'scale') or (label == 'wirecolor'):
                # We don't need any of this as we'll take it directly from
                # the object
                pass
            else:
                # We'll take everything that doesn't start with a #
                if label[0] != '#':
                    asciiLines.append('  ' + ' '.join(line))


class Light(GeometryNode):
    def __init__(self, name = 'UNNAMED'):
        GeometryNode.__init__(self, name)
        self.nodetype = 'light'

        self.shadow        = 1
        self.radius        = 5.0
        self.multiplier    = 1
        self.lightpriority = 5
        self.color         = (0.0, 0.0, 0.0)
        self.ambientonly   = 1
        self.ndynamictype  = 0
        self.isdynamic     = 0
        self.affectdynamic = 1
        self.negativelight = 0
        self.fadinglight   = 1
        self.lensflares    = 0
        self.flareradius   = 1.0
        self.flareList     = FlareList()

    def loadAscii(self, asciiNode):
        GeometryNode.loadAscii(self, asciiNode)

        flareTextureNamesStart = 0
        numFlares              = 0
        numVals                = 0

        l_int = int
        l_float = float
        l_isNumber = nvb_utils.isNumber
        for idx, line in enumerate(asciiNode):
            try:
                label = line[0].lower()
            except IndexError:
                # Probably empty line or whatever, skip it
                continue

            if not l_isNumber(label):
                if (label == 'radius'):
                    self.radius = l_float(line[1])
                    self.parsed_lines.append(idx)
                elif (label == 'shadow'):
                    self.shadow = l_int(line[1])
                    self.parsed_lines.append(idx)
                elif (label == 'multiplier'):
                    self.multiplier = l_float(line[1])
                    self.parsed_lines.append(idx)
                elif (label == 'color'):
                    self.color = (l_float(line[1]),
                                  l_float(line[2]),
                                  l_float(line[3]))
                    self.parsed_lines.append(idx)
                elif (label == 'ambientonly'):
                    self.ambientonly = l_int(line[1])
                    self.parsed_lines.append(idx)
                elif (label == 'ndynamictype'):
                    self.ndynamictype = l_int(line[1])
                    self.parsed_lines.append(idx)
                elif (label == 'isdynamic'):
                    self.isdynamic = l_int(line[1])
                    self.parsed_lines.append(idx)
                elif (label == 'affectdynamic'):
                    self.affectdynamic = l_int(line[1])
                    self.parsed_lines.append(idx)
                elif (label == 'negativelight'):
                    self.negativelight = l_int(line[1])
                    self.parsed_lines.append(idx)
                elif (label == 'lightpriority'):
                    self.lightpriority = l_int(line[1])
                    self.parsed_lines.append(idx)
                elif (label == 'fadinglight'):
                    self.fadinglight = l_int(line[1])
                    self.parsed_lines.append(idx)
                elif (label == 'lensflares'):
                    self.lensflares = l_int(line[1])
                    self.parsed_lines.append(idx)
                elif (label == 'flareradius'):
                    self.flareradius = l_float(line[1])
                    self.parsed_lines.append(idx)
                elif (label == 'texturenames'):
                    # List of names follows, but we don't necessarily know how
                    # many flares there are
                    # We 'll need to read them later. For now save the index
                    flareTextureNamesStart = idx+1
                    self.parsed_lines.append(idx)
                elif (label == 'flaresizes'):
                    # List of floats
                    numVals = next((i for i, v in enumerate(asciiNode[idx+1:]) if not l_isNumber(v[0])), -1)
                    nvb_parse.f1(asciiNode[idx+1:idx+numVals+1], self.flareList.sizes)
                    #self.flareList.sizes = [float(l[0]) for l in asciiNode[idx+1:idx+numVals+1]]
                    self.parsed_lines.extend(range(idx,idx+numVals+1))
                elif (label == 'flarepositions'):
                    # List of floats
                    numVals = next((i for i, v in enumerate(asciiNode[idx+1:]) if not l_isNumber(v[0])), -1)
                    nvb_parse.f1(asciiNode[idx+1:idx+numVals+1], self.flareList.positions)
                    #self.flareList.positions = [float(l[0]) for l in asciiNode[idx+1:idx+numVals+1]]
                    self.parsed_lines.extend(range(idx,idx+numVals+1))
                elif (label == 'flarecolorshifts'):
                    # List of float 3-tuples
                    numVals = next((i for i, v in enumerate(asciiNode[idx+1:]) if not l_isNumber(v[0])), -1)
                    nvb_parse.f3(asciiNode[idx+1:idx+numVals+1], self.flareList.colorshifts)
                    #self.flareList.colorshifts = [(float(l[0]), float(l[1]), float(l[2])) for l in asciiNode[idx+1:idx+numVals+1]]
                    self.parsed_lines.extend(range(idx,idx+numVals+1))

        # Load flare texture names:
        numFlares = min(len(self.flareList.sizes),
                        min(len(self.flareList.colorshifts),
                            len(self.flareList.positions)))
        for i in range(numFlares):
            texName = asciiNode[flareTextureNamesStart+i][0]
            self.flareList.textures.append(texName)
            self.parsed_lines.append(flareTextureNamesStart+i)

        if (self.nodetype == 'light'):
            self.addUnparsedToRaw(asciiNode)

    def createLamp(self, name):
        lamp = bpy.data.lamps.new(name, 'POINT')

        # TODO: Check for negative color values and do something (works fine in blender though)
        if self.color[0] < 0.0 or self.color[1] < 0.0 or self.color[2] < 0.0:
            lamp.use_negative = True
            self.color = (0.0 - self.color[0],
                          0.0 - self.color[1],
                          0.0 - self.color[2])
        lamp.color       = self.color
        lamp.energy      = self.multiplier
        lamp.distance    = self.radius
        #lamp.use_sphere  = True
        if self.shadow == 1:
            lamp.shadow_method = 'RAY_SHADOW'

        return lamp

    def setObjectData(self, obj):
        GeometryNode.setObjectData(self, obj)

        switch = {'ml1': 'MAINLIGHT1',
                  'ml2': 'MAINLIGHT2',
                  'sl1': 'SOURCELIGHT1',
                  'sl2': 'SOURCELIGHT2'}
        #TODO: Check light names when exporting tiles
        obj.nvb.ambientonly   = (self.ambientonly >= 1)
        obj.nvb.lighttype     = switch.get(self.name[-3:], 'NONE')
        obj.nvb.shadow        = (self.shadow >= 1)
        obj.nvb.lightpriority = self.lightpriority
        obj.nvb.fadinglight   = (self.fadinglight >= 1)
        obj.nvb.isdynamic     = self.ndynamictype
        if obj.nvb.isdynamic == 0 and self.isdynamic >= 1:
            obj.nvb.isdynamic = 1
        obj.nvb.affectdynamic = (self.affectdynamic >= 1)

        if (self.flareradius > 0) or (self.lensflares >= 1):
            obj.nvb.lensflares = True
            numFlares = len(self.flareList.textures)
            for i in range(numFlares):
                newItem = obj.nvb.flareList.add()
                newItem.texture    = self.flareList.textures[i]
                newItem.colorshift = self.flareList.colorshifts[i]
                newItem.size       = self.flareList.sizes[i]
                newItem.position   = self.flareList.positions[i]

        obj.nvb.flareradius = self.flareradius

    def addToScene(self, scene):
        if nvb_glob.minimapMode:
            # We don't need lights in minimap mode
            # We may need it for the tree stucture, so import it as an empty
            return GeometryNode.addToScene(self, scene)
        lamp = self.createLamp(self.name)
        obj  = bpy.data.objects.new(self.name, lamp)
        self.setObjectData(obj)
        scene.objects.link(obj)
        return obj

    def addFlaresToAscii(self, obj, asciiLines):
        if obj.nvb.lensflares:
            asciiLines.append('  lensflares ' + str(int(obj.nvb.lensflares)))
            # print(str(len(obj.nvb.flareList)))
            if len(obj.nvb.flareList) > 0:

                # TODO: Clean this up
                asciiLines.append('  texturenames zd')
                for flare in obj.nvb.flareList:
                    asciiLines.append('    ' + flare.texture)
                asciiLines.append('  flarepositions zd')
                for flare in obj.nvb.flareList:
                    asciiLines.append('    ' + str(round(flare.position, 7)))
                asciiLines.append('  flaresizes zd')
                for flare in obj.nvb.flareList:
                    asciiLines.append('    ' + str(flare.size))
                asciiLines.append('  flarecolorshifts zd')
                for flare in obj.nvb.flareList:
                    asciiLines.append('    ' +  str(round(flare.colorshift[0], 2)) + ' ' +
                                                str(round(flare.colorshift[1], 2)) + ' ' +
                                                str(round(flare.colorshift[2], 2)) )
        asciiLines.append('  flareradius ' + str(round(obj.nvb.flareradius, 1)))

    def addDataToAscii(self, obj, asciiLines, classification = nvb_def.Classification.UNKNOWN, simple = False, nameDict=None):
        GeometryNode.addDataToAscii(self, obj, asciiLines, classification, nameDict=nameDict)

        lamp = obj.data
        color = (lamp.color[0], lamp.color[1], lamp.color[2])
        if lamp.use_negative:
            color[0] = 0.0 - lamp.color[0]
            color[1] = 0.0 - lamp.color[1]
            color[2] = 0.0 - lamp.color[2]
        asciiLines.append('  radius ' + str(round(lamp.distance, 1)))
        asciiLines.append('  multiplier ' + str(round(lamp.energy, 1)))
        asciiLines.append('  color ' +  str(round(color[0], 2)) + ' ' +
                                        str(round(color[1], 2)) + ' ' +
                                        str(round(color[2], 2)))
        asciiLines.append('  ambientonly ' + str(int(obj.nvb.ambientonly)))
        asciiLines.append('  nDynamicType ' + str(obj.nvb.isdynamic))
        asciiLines.append('  affectDynamic ' + str(int(obj.nvb.affectdynamic)))
        asciiLines.append('  shadow ' + str(int(obj.nvb.shadow)))
        asciiLines.append('  lightpriority ' + str(obj.nvb.lightpriority))
        asciiLines.append('  fadingLight ' + str(int(obj.nvb.fadinglight)))
        self.addFlaresToAscii(obj, asciiLines)


class Aabb(Trimesh):
    '''
    No need to import Aaabb's. Aabb nodes in mdl files will be
    treated as trimeshes
    '''
    def __init__(self, name = 'UNNAMED'):
        Trimesh.__init__(self, name)
        self.nodetype = 'aabb'

        self.meshtype = nvb_def.Meshtype.AABB

    def computeLayoutPosition(self, wkm):
        wkmv1 = wkm.verts[wkm.facelist.faces[0][0]]
        wkmv1 = (wkmv1[0] - wkm.position[0],
                 wkmv1[1] - wkm.position[1],
                 wkmv1[2] - wkm.position[2])
        #print(wkmv1)
        for faceIdx, face in enumerate(self.facelist.faces):
            if self.facelist.matId[faceIdx] != 7:
                v1 = self.verts[face[0]]
                #print(v1)
                self.lytposition = (round(wkmv1[0] - v1[0], 6),
                                    round(wkmv1[1] - v1[1], 6),
                                    round(wkmv1[2] - v1[2], 6))
                break
        bpy.data.objects[self.name].nvb.lytposition = self.lytposition
        #pprint(bpy.data.objects[self.name])

    def addAABBToAscii(self, obj, asciiLines):
        walkmesh = obj.to_mesh(nvb_glob.scene, nvb_glob.applyModifiers, nvb_glob.meshConvert)

        faceList = []
        faceIdx  = 0
        for tessface in walkmesh.tessfaces:
            if (len(tessface.vertices) == 3):
                # Tri
                v0 = tessface.vertices[0]
                v1 = tessface.vertices[1]
                v2 = tessface.vertices[2]

                centroid = mathutils.Vector((walkmesh.vertices[v0].co + walkmesh.vertices[v1].co + walkmesh.vertices[v2].co)/3)
                faceList.append((faceIdx, [walkmesh.vertices[v0].co, walkmesh.vertices[v1].co, walkmesh.vertices[v2].co], centroid))
                faceIdx += 1

            elif (len(tessface.vertices) == 4):
                # Quad
                v0 = tessface.vertices[0]
                v1 = tessface.vertices[1]
                v2 = tessface.vertices[2]
                v3 = tessface.vertices[3]

                centroid = mathutils.Vector((walkmesh.vertices[v0].co + walkmesh.vertices[v1].co + walkmesh.vertices[v2].co)/3)
                faceList.append((faceIdx, [walkmesh.vertices[v0].co, walkmesh.vertices[v1].co, walkmesh.vertices[v2].co], centroid))
                faceIdx += 1

                centroid = mathutils.Vector((walkmesh.vertices[v2].co + walkmesh.vertices[v3].co + walkmesh.vertices[v0].co)/3)
                faceList.append((faceIdx, [walkmesh.vertices[v2].co, walkmesh.vertices[v3].co, walkmesh.vertices[v0].co], centroid))
                faceIdx += 1
            else:
                # Ngon or no polygon at all (This should never be the case with tessfaces)
                print('Kotorblender - WARNING: Ngon in walkmesh. Unable to generate aabb.')
                return

        aabbTree = []
        nvb_aabb.generateTree(aabbTree, faceList)

        l_round = round
        if aabbTree:
            node = aabbTree.pop(0)
            asciiLines.append('  aabb  ' +
                              ' ' +
                              str(l_round(node[0], 7)) +
                              ' ' +
                              str(l_round(node[1], 7)) +
                              ' ' +
                              str(l_round(node[2], 7)) +
                              ' ' +
                              str(l_round(node[3], 7)) +
                              ' ' +
                              str(l_round(node[4], 7)) +
                              ' ' +
                              str(l_round(node[5], 7)) +
                              ' ' +
                              str(node[6]))
            for node in aabbTree:
                asciiLines.append('    ' +
                                  str(l_round(node[0], 7)) +
                                  ' ' +
                                  str(l_round(node[1], 7)) +
                                  ' ' +
                                  str(l_round(node[2], 7)) +
                                  ' ' +
                                  str(l_round(node[3], 7)) +
                                  ' ' +
                                  str(l_round(node[4], 7)) +
                                  ' ' +
                                  str(l_round(node[5], 7)) +
                                  ' ' +
                                  str(node[6]) )


    def addDataToAscii(self, obj, asciiLines, classification = nvb_def.Classification.UNKNOWN, simple = False, nameDict=None):
        if obj.parent and nameDict and obj.parent.name in nameDict:
            asciiLines.append('  parent ' + nameDict[obj.parent.name])
        elif obj.parent:
            asciiLines.append('  parent ' + obj.parent.name)
        else:
            asciiLines.append('  parent ' + nvb_def.null)
        loc = obj.location
        asciiLines.append('  position ' + str(round(loc[0], 7)) + ' ' +
                                          str(round(loc[1], 7)) + ' ' +
                                          str(round(loc[2], 7)) )
        rot = nvb_utils.getAuroraRotFromObject(obj)
        asciiLines.append('  orientation ' + str(round(rot[0], 7)) + ' ' +
                                             str(round(rot[1], 7)) + ' ' +
                                             str(round(rot[2], 7)) + ' ' +
                                             str(round(rot[3], 7)) )
        color = obj.nvb.wirecolor
        asciiLines.append('  wirecolor ' + str(round(color[0], 2)) + ' ' +
                                           str(round(color[1], 2)) + ' ' +
                                           str(round(color[2], 2))  )
        asciiLines.append('  ambient 1.0 1.0 1.0')
        asciiLines.append('  diffuse 1.0 1.0 1.0')
        asciiLines.append('  bitmap NULL')
        Trimesh.addMeshDataToAscii(self, obj, asciiLines, simple)
        if self.roottype != 'wok':
            self.addAABBToAscii(obj, asciiLines)


    def createMesh(self, name):
        # Create the mesh itself
        mesh = bpy.data.meshes.new(name)
        mesh.vertices.add(len(self.verts))
        mesh.vertices.foreach_set('co', unpack_list(self.verts))
        mesh.tessfaces.add(len(self.facelist.faces))
        mesh.tessfaces.foreach_set('vertices_raw', unpack_face_list(self.facelist.faces))

        # Create materials
        for wokMat in nvb_def.wok_materials:
            matName = wokMat[0]
            # Walkmesh materials will be shared across multiple walkmesh
            # objects
            if matName in bpy.data.materials:
                material = bpy.data.materials[matName]
            else:
                material = bpy.data.materials.new(matName)
                material.diffuse_color      = wokMat[1]
                material.diffuse_intensity  = 1.0
                material.specular_color     = (0.0,0.0,0.0)
                material.specular_intensity = wokMat[2]
            mesh.materials.append(material)

        # Create UV map
        uv = None
        if (len(self.tverts) > 0) and (mesh.tessfaces):
            uv = mesh.tessface_uv_textures.new(name + '.uv')
            mesh.tessface_uv_textures.active = uv

        # Apply the walkmesh materials to each face
        for idx, face in enumerate(mesh.tessfaces):
            face.material_index = self.facelist.matId[idx]
            if uv:
                faceUV = mesh.tessface_uv_textures[0].data[idx]
                uvIdx = self.facelist.uvIdx[idx]
                if self.facelist.faces[idx][2] == 0:
                    uvIdx = uvIdx[1], uvIdx[2], uvIdx[0]
                faceUV.uv1 = self.tverts[uvIdx[0]]
                faceUV.uv2 = self.tverts[uvIdx[1]]
                faceUV.uv3 = self.tverts[uvIdx[2]]
                # Apply texture to uv face
                #if (not nvb_utils.isNull(self.bitmap)) and material.texture_slots[0]:
                #    faceUV.image = material.texture_slots[0].texture.image

        mesh.update()
        return mesh


    def addToScene(self, scene):
        if nvb_glob.minimapMode:
            # No walkmeshes in minimap mode and we don't need an empty as
            # replacement either as AABB nodes never have children
            return GeometryNode.addToScene(self, scene)
        mesh = self.createMesh(self.name)
        obj = bpy.data.objects.new(self.name, mesh)
        self.setObjectData(obj)
        scene.objects.link(obj)
        return obj
