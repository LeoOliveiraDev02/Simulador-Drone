"""Converte um arquivo STEP (CAD) em .glb mantendo nomes das peças e cores.

Uso: python step_para_glb.py entrada.step saida.glb [deflexao_mm]
Precisa de: pip install cadquery-ocp
"""
import sys

from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.IFSelect import IFSelect_RetDone
from OCP.Message import Message_ProgressRange
from OCP.RWGltf import RWGltf_CafWriter, RWGltf_WriterTrsfFormat
from OCP.RWMesh import RWMesh_CoordinateSystem
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TCollection import TCollection_AsciiString, TCollection_ExtendedString
from OCP.collections import IndexedDataMap_TCollection_AsciiString_TCollection_AsciiString as MapaInfo
from OCP.collections import Sequence_TDF_Label as TDF_LabelSequence
from OCP.TDocStd import TDocStd_Document
from OCP.XCAFDoc import XCAFDoc_DocumentTool


def main():
    entrada, saida = sys.argv[1], sys.argv[2]
    deflexao = float(sys.argv[3]) if len(sys.argv) > 3 else 0.05

    doc = TDocStd_Document(TCollection_ExtendedString("XmlOcaf"))
    leitor = STEPCAFControl_Reader()
    leitor.SetColorMode(True)
    leitor.SetNameMode(True)
    leitor.SetLayerMode(True)
    if leitor.ReadFile(entrada) != IFSelect_RetDone:
        raise SystemExit("Falha ao ler " + entrada)
    leitor.Transfer(doc)

    ferramenta = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    livres = TDF_LabelSequence()
    ferramenta.GetFreeShapes(livres)
    for i in range(1, livres.Length() + 1):
        forma = ferramenta.GetShape_s(livres.Value(i))
        BRepMesh_IncrementalMesh(forma, deflexao, False, 0.35, True)

    escritor = RWGltf_CafWriter(TCollection_AsciiString(saida), True)
    escritor.SetTransformationFormat(RWGltf_WriterTrsfFormat.RWGltf_WriterTrsfFormat_TRS)
    conv = escritor.ChangeCoordinateSystemConverter()
    conv.SetInputLengthUnit(0.001)  # STEP em milímetros
    conv.SetInputCoordinateSystem(RWMesh_CoordinateSystem.RWMesh_CoordinateSystem_Zup)
    conv.SetOutputLengthUnit(1.0)  # glTF em metros
    conv.SetOutputCoordinateSystem(RWMesh_CoordinateSystem.RWMesh_CoordinateSystem_glTF)
    info = MapaInfo()
    if not escritor.Perform(doc, info, Message_ProgressRange()):
        raise SystemExit("Falha ao gravar " + saida)
    print("ok", saida)


if __name__ == "__main__":
    main()
