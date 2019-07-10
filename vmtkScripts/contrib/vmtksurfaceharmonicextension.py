#!/usr/bin/env python

## Program:   VMTK
## Module:    $RCSfile: vmtksurfaceviewer.py,v $
## Language:  Python
## Date:      $Date: 2006/05/26 12:35:13 $
## Version:   $Revision: 1.10 $

##   Copyright (c) Luca Antiga, David Steinman. All rights reserved.
##   See LICENCE file for details.

##      This software is distributed WITHOUT ANY WARRANTY; without even 
##      the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR 
##      PURPOSE.  See the above copyright notices for more information.

## Note: this class was contributed by 
##       Elena Faggiano (elena.faggiano@gmail.com)
##       Politecnico di Milano

from __future__ import absolute_import #NEEDS TO STAY AS TOP LEVEL MODULE FOR Py2-3 COMPATIBILITY
import vtk
import sys


from vmtk import pypes


vmtksurfaceharmonicextension = 'vmtkSurfaceHarmonicExtension'

class vmtkSurfaceHarmonicExtension(pypes.pypeScript):

    def __init__(self):

        pypes.pypeScript.__init__(self)

        self.Surface = None
        self.InputArrayName = 'Displacement'
        self.OutputArrayName = 'DisplacementOut'
        self.InputArray = None
        self.OutputArray = None
        self.RangeIds = None
        self.OutletIds = []
        self.MethodX = "harmonic"
        self.MethodY = "harmonic"
        self.MethodZ = "harmonic"
        self.ProjectionMethod = "surface"
        self.BoundaryConditions = []
        self.CellEntityIdsArrayName = 'CellEntityIds'
        self.CellEntityIdsArray = None


        self.SetScriptName('vmtksurfaceharmonicextension')
        self.SetScriptDoc('extend an input vector harmonically on a surface')
        self.SetInputMembers([
            ['Surface','i','vtkPolyData',1,'','the input surface','vmtksurfacereader'],
            ['InputArrayName','inputarray','str',1,'','input array to be extended on some tags'],
            ['OutputArrayName','outputarray','str',1,'','output array name'],
            ['RangeIds','rangeids','int',2,'','range of ids where to extend the input array'],
            ['OutletIds','outletids','int',-1,'','ids where to impose the heat equation bcs (these ids must be in rangeids)'],
            ['MethodX','methodx','str',1,'["harmonic","projection","meanring"]','possible extensions methods'],
            ['MethodY','methody','str',1,'["harmonic","projection","menaring"]','possible extensions methods'],
            ['MethodZ','methodz','str',1,'["harmonic","projection","meanring"]','possible extensions methods'],
            ['ProjectionMethod','projectionmethod','str',1,'["surface","ring","none"]','possible projection methods'],
            ['BoundaryConditions','bcs','float',-1,'','list of bcs for the harmonic extension outlets, ordered as boundary id'],
            ['CellEntityIdsArrayName', 'entityidsarray', 'str', 1, '','name of the array where entity ids have been stored'],
            ])
        self.SetOutputMembers([
            ['Surface','o','vtkPolyData',1,'','the output surface','vmtksurfacewriter']
            ])


    def Execute(self): 
        from vmtk import vtkvmtk
        from vmtk import vmtkscripts
        from vmtk import vmtkcontribscripts

        if self.Surface == None:
            self.PrintError('Error: no Surface.')

        self.CellEntityIdsArray = self.Surface.GetCellData().GetArray(self.CellEntityIdsArrayName)

        tags = set()
        for i in range(self.Surface.GetNumberOfCells()):
            tags.add(self.CellEntityIdsArray.GetComponent(i,0))
        tags = sorted(tags)
        self.PrintLog('Tags of the input surface: '+str(tags))


        def surfaceThreshold(surface,low,high):
            th = vmtkcontribscripts.vmtkThreshold()
            th.Surface = surface
            th.CellEntityIdsArrayName = self.CellEntityIdsArrayName
            th.LowThreshold = low
            th.HighThreshold = high
            th.Execute()
            surf = th.Surface
            return surf

        def surfaceAppend(surface1,surface2):
            if surface1 == None:
                surf = surface2
            elif surface2 == None:
                surf = surface1
            else:
                a = vmtkscripts.vmtkSurfaceAppend()
                a.Surface = surface1
                a.Surface2 = surface2
                a.Execute()
                surf = a.Surface 
                tr = vmtkscripts.vmtkSurfaceTriangle()
                tr.Surface = surf
                tr.Execute()
                surf = tr.Surface
            return surf

        def surfaceProjection(isurface,rsurface):
            proj = vmtkscripts.vmtkSurfaceProjection()
            proj.Surface = isurface
            proj.ReferenceSurface = rsurface
            proj.Execute()
            return proj.Surface


        surfaceHarmonicCaps = None
        surfaceHarmonicDomain = None
        surfaceNotProcessed = None

        for item in tags:
            surfaceTh = surfaceThreshold(self.Surface,item,item)
            if item <= self.RangeIds[1] and item >= self.RangeIds[0]:
                if item in self.OutletIds:
                    surfaceHarmonicCaps = surfaceAppend(surfaceHarmonicCaps,surfaceTh)
                else:
                    surfaceHarmonicDomain = surfaceAppend(surfaceHarmonicDomain,surfaceTh)
            else:
                surfaceNotProcessed = surfaceAppend(surfaceNotProcessed,surfaceTh)


        meanRingX = 0.0
        meanRingY = 0.0
        meanRingZ = 0.0

        # if metodo closest point
        # proietta il valore di InputArray da surfaceNotProcessed a surfaceHarmonic
        if self.ProjectionMethod == "surface":
            surfaceHarmonicCaps = surfaceProjection(surfaceHarmonicCaps,surfaceNotProcessed)
            surfaceHarmonicDomain = surfaceProjection(surfaceHarmonicDomain,surfaceNotProcessed)
        
        # if metodo ring:
        # estrai i ring da surfaceNotProcessed
        # proietta il valore di InputArray nel ring su surfaceHarmonic
        elif self.ProjectionMethod == "ring":
            fe = vtk.vtkFeatureEdges()
            fe.BoundaryEdgesOn()
            fe.FeatureEdgesOff()
            fe.NonManifoldEdgesOff()
            fe.ManifoldEdgesOff()
            fe.ColoringOff()
            fe.SetInputData(surfaceNotProcessed)
            fe.CreateDefaultLocator()
            fe.Update()
            rings = fe.GetOutput()
            surfaceHarmonicCaps = surfaceProjection(surfaceHarmonicCaps,rings)
            surfaceHarmonicDomain = surfaceProjection(surfaceHarmonicDomain,rings)
            # compute mean ring
            ringInputArray = rings.GetPointData().GetArray(self.InputArrayName)
            numRingPoints = rings.GetNumberOfPoints()
            for i in range(numRingPoints):
                meanRingX = meanRingX + ringInputArray.GetComponent(i,0)
                meanRingY = meanRingY + ringInputArray.GetComponent(i,1)
                meanRingZ = meanRingZ + ringInputArray.GetComponent(i,2)
            meanRingX = meanRingX / numRingPoints
            meanRingY = meanRingY / numRingPoints
            meanRingZ = meanRingZ / numRingPoints

        else:
            self.PrintLog("No projection active")


        hs = vmtkcontribscripts.vmtkSurfaceHarmonicSections()
        hs.Surface = surfaceHarmonicDomain
        hs.ComputeSections = 0
        hs.BoundaryConditions = self.BoundaryConditions
        hs.Execute()
        surfaceHarmonicDomain = hs.SurfaceHarmonic

        uCaps = vtk.vtkDoubleArray()
        uCaps.SetNumberOfComponents(1)
        uCaps.SetNumberOfTuples(surfaceHarmonicCaps.GetNumberOfPoints())
        uCaps.SetName('HarmonicMappedTemperature')
        uCaps.FillComponent(0,0.0)
        surfaceHarmonicCaps.GetPointData().AddArray(uCaps)

        uNotProcessed = vtk.vtkDoubleArray()
        uNotProcessed.SetNumberOfComponents(1)
        uNotProcessed.SetNumberOfTuples(surfaceNotProcessed.GetNumberOfPoints())
        uNotProcessed.SetName('HarmonicMappedTemperature')
        uNotProcessed.FillComponent(0,1.0)
        surfaceNotProcessed.GetPointData().AddArray(uNotProcessed)

        surfaceHarmonic = surfaceAppend(surfaceHarmonicDomain,surfaceHarmonicCaps)
        self.Surface = surfaceAppend(surfaceHarmonic,surfaceNotProcessed)

        u = self.Surface.GetPointData().GetArray('HarmonicMappedTemperature')
        for i in range(u.GetNumberOfTuples()):
            if u.GetTuple1(i) < 0.0:
                u.SetTuple1(i,0.0)

        self.InputArray = self.Surface.GetPointData().GetArray(self.InputArrayName)
        self.OutputArray = vtk.vtkDoubleArray()
        self.OutputArray.SetNumberOfComponents(3)
        self.OutputArray.SetNumberOfTuples(self.Surface.GetNumberOfPoints())
        self.OutputArray.SetName(self.OutputArrayName)

        for i in range(self.OutputArray.GetNumberOfTuples()):
            val = self.InputArray.GetComponent(i,0)
            if self.MethodX == "harmonic":
                val = val * u.GetTuple1(i)
            elif self.MethodX == "meanring":
                val = (val - meanRingX) * u.GetTuple1(i) + meanRingX
            self.OutputArray.SetComponent(i,0,val)

            val = self.InputArray.GetComponent(i,1)
            if self.MethodY == "harmonic":
                val = val * u.GetTuple1(i)
            elif self.MethodY == "meanring":
                val = (val - meanRingY) * u.GetTuple1(i) + meanRingY
            self.OutputArray.SetComponent(i,1,val)

            val = self.InputArray.GetComponent(i,2)
            if self.MethodZ == "harmonic":
                val = val * u.GetTuple1(i)
            elif self.MethodZ == "meanring":
                val = (val - meanRingZ) * u.GetTuple1(i) + meanRingZ
            self.OutputArray.SetComponent(i,2,val)
            # mean ring 
            # sposti di: [ val - mean(ring) ] * u + mean(ring)
        

        self.Surface.GetPointData().AddArray(self.OutputArray)
        # self.Surface = surfaceHarmonicDomain

        


if __name__=='__main__':
    main = pypes.pypeMain()
    main.Arguments = sys.argv
    main.Execute()