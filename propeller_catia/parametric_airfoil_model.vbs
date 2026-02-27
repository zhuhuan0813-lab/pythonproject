Sub CATMain()
    ' 获取 CATIA 应用程序
    Dim CATIA
    On Error Resume Next
    Set CATIA = GetObject(, "CATIA.Application")
    If Err.Number <> 0 Then
        Set CATIA = CreateObject("CATIA.Application")
        CATIA.Visible = True
    End If
    On Error GoTo 0

    Set documents1 = CATIA.Documents
    Set partDocument1 = documents1.Add("Part")
    Set part1 = partDocument1.Part
    Set hybridShapeFactory1 = part1.HybridShapeFactory
    Set parameters1 = part1.Parameters

    ' ------------------- 参数定义（可修改区域）-------------------
    Dim rotor_diameter, root_chord, mid_chord, tip_chord
    Dim hub_cone_angle, root_twist, mid_twist, tip_twist
    Dim mid_position_ratio

    ' 几何参数（单位：mm）
    rotor_diameter = 7620.000000     ' 旋翼直径
    root_chord = 431.800000         ' 翼根弦长
    mid_chord = 368.300000          ' 翼中弦长
    tip_chord = 304.800000          ' 翼尖弦长

    ' 角度参数（单位：度）
    hub_cone_angle = 1.500000       ' 桨毂前锥角
    root_twist = 40.250000          ' 翼根扭转角
    mid_twist = 18.250000           ' 翼中扭转角
    tip_twist = -3.750000           ' 翼尖扭转角

    ' 位置参数
    mid_position_ratio = 0.500000   ' 翼中位置比例（0-1，相对半径）

    ' 原始翼型弦长（dat文件中的弦长）
    Dim original_chord: original_chord = 99.000000
    ' -------------------------------------------------------------

    ' 创建参数
    Set length1 = parameters1.CreateDimension("", "LENGTH", rotor_diameter)
    length1.Rename "旋翼直径"

    Set length2 = parameters1.CreateDimension("", "LENGTH", root_chord)
    length2.Rename "翼根弦长"

    Set length3 = parameters1.CreateDimension("", "LENGTH", mid_chord)
    length3.Rename "翼中弦长"

    Set length4 = parameters1.CreateDimension("", "LENGTH", tip_chord)
    length4.Rename "翼尖弦长"

    Set angle1 = parameters1.CreateDimension("", "ANGLE", hub_cone_angle)
    angle1.Rename "桨毂前锥角"

    Set angle2 = parameters1.CreateDimension("", "ANGLE", root_twist)
    angle2.Rename "翼根扭转角"

    Set angle3 = parameters1.CreateDimension("", "ANGLE", mid_twist)
    angle3.Rename "翼中扭转角"

    Set angle4 = parameters1.CreateDimension("", "ANGLE", tip_twist)
    angle4.Rename "翼尖扭转角"

    Set realParam1 = parameters1.CreateReal("", mid_position_ratio)
    realParam1.Rename "翼中所在位置比例"

    ' 创建几何图形集
    Set hybridBodies1 = part1.HybridBodies
    Set hybridBody1 = hybridBodies1.Add()
    hybridBody1.Name = "桨叶GS"

    Set hybridBodies2 = hybridBody1.HybridBodies
    Set hybridBody2 = hybridBodies2.Add()
    hybridBody2.Name = "翼型"

    Set hybridBodies2 = hybridBody1.HybridBodies
    Set hybridBody3 = hybridBodies2.Add()
    hybridBody3.Name = "参考"

    ' 创建原点
    Set hybridShapePointCoord1 = hybridShapeFactory1.AddNewPointCoord(0.000000, 0.000000, 0.000000)
    hybridBody3.AppendHybridShape hybridShapePointCoord1

    ' 创建径向轴线（Y轴方向）
    Set hybridShapeDirection4 = hybridShapeFactory1.AddNewDirectionByCoord(0.000000, 1.000000, 0.000000)
    Set reference933 = part1.CreateReferenceFromObject(hybridShapePointCoord1)
    Set hybridShapeLinePtDir1 = hybridShapeFactory1.AddNewLinePtDir( _
        reference933, hybridShapeDirection4, 0.000000, rotor_diameter / 2, False)
    hybridBody1.AppendHybridShape hybridShapeLinePtDir1

    ' 创建翼中位置点
    Set reference934 = part1.CreateReferenceFromObject(hybridShapeLinePtDir1)
    Set hybridShapePointOnCurve1 = hybridShapeFactory1.AddNewPointOnCurveFromPercent( _
        reference934, mid_position_ratio, False)
    hybridBody1.AppendHybridShape hybridShapePointOnCurve1

    ' 计算缩放比例（参数化）
    Dim root_scale, mid_scale, tip_scale
    root_scale = root_chord / original_chord
    mid_scale = mid_chord / original_chord
    tip_scale = tip_chord / original_chord

    MsgBox "参数化计算完成！" & vbCrLf & _
           "翼根缩放: " & FormatNumber(root_scale, 6) & vbCrLf & _
           "翼中缩放: " & FormatNumber(mid_scale, 6) & vbCrLf & _
           "翼尖缩放: " & FormatNumber(tip_scale, 6)

    ' 创建三个翼型的几何图形集
    Dim airfoilNames, airfoilScales, airfoilTwists
    airfoilNames = Array("NAVA64-528", "NAVA64-118", "NAVA64-208")
    airfoilScales = Array(root_scale, mid_scale, tip_scale)
    airfoilTwists = Array(root_twist, mid_twist, tip_twist)

    Dim i
    For i = 0 To 2
        Set hybridBodies3 = hybridBody2.HybridBodies
        Set hybridBodyN = hybridBodies3.Add()
        hybridBodyN.Name = airfoilNames(i)

        Set hybridBodiesN = hybridBodyN.HybridBodies
        Set hybridBodyPoints = hybridBodiesN.Add()
        hybridBodyPoints.Name = "点"

        ' 这里可以添加读取 dat 文件的代码
        ' 为简化演示，这里只创建一个简单的翼型
        Call CreateSimpleAirfoil(hybridShapeFactory1, hybridBodyPoints, original_chord)

        ' 创建样条曲线
        Set hybridShapesPoints = hybridBodyPoints.HybridShapes
        Dim references()
        ReDim references(hybridShapesPoints.Count - 1)

        Dim j
        For j = 0 To hybridShapesPoints.Count - 1
            Set references(j) = part1.CreateReferenceFromObject(hybridShapesPoints.Item(j + 1))
        Next

        Set hybridShapeSpline = hybridShapeFactory1.AddNewSpline()
        hybridShapeSpline.SetSplineType 0
        hybridShapeSpline.SetClosing 0

        For j = 0 To UBound(references)
            hybridShapeSpline.AddPoint references(j)
        Next

        hybridShapeSpline.Name = "Spline.1"
        hybridBodyN.AppendHybridShape hybridShapeSpline

        ' 创建平移变换
        Set hybridShapeTranslate = hybridShapeFactory1.AddNewEmptyTranslate()
        Set refSpline = part1.CreateReferenceFromObject(hybridShapeSpline)
        hybridShapeTranslate.ElemToTranslate = refSpline
        hybridShapeTranslate.VectorType = 1

        If i = 0 Then ' 翼根
            Set hybridShapeTranslate.FirstPoint = reference933 ' 原点
            hybridShapeTranslate.SecondPoint = reference933 ' 原点
        ElseIf i = 1 Then ' 翼中
            Set refMidPoint = part1.CreateReferenceFromObject(hybridShapePointOnCurve1)
            Set hybridShapeTranslate.FirstPoint = reference933
            hybridShapeTranslate.SecondPoint = refMidPoint
        Else ' 翼尖
            Set refTipPoint = part1.CreateReferenceFromBRepName( _
                "BorderFVertex:(BEdge:(Brp:(GSMLine.1;2);None:(Limits1:();Limits2:();-1);Cf11:());" & _
                "WithPermanentBody;WithoutBuildError;WithSelectingFeatureSupport;MFBRepVersion_CXR15)", _
                hybridShapeLinePtDir1)
            Set hybridShapeTranslate.FirstPoint = reference933
            hybridShapeTranslate.SecondPoint = refTipPoint
        End If

        hybridShapeTranslate.Name = "Translate." & (i + 1)
        hybridBodyN.AppendHybridShape hybridShapeTranslate

        ' 创建缩放变换
        Dim refTargetPoint
        If i = 0 Then
            refTargetPoint = reference933
        ElseIf i = 1 Then
            Set refTargetPoint = part1.CreateReferenceFromObject(hybridShapePointOnCurve1)
        Else
            Set refTargetPoint = part1.CreateReferenceFromBRepName( _
                "BorderFVertex:(BEdge:(Brp:(GSMLine.1;2);None:(Limits1:();Limits2:();-1);Cf11:());" & _
                "WithPermanentBody;WithoutBuildError;WithSelectingFeatureSupport;MFBRepVersion_CXR15)", _
                hybridShapeLinePtDir1)
        End If

        Set refTranslate = part1.CreateReferenceFromObject(hybridShapeTranslate)
        Set hybridShapeScaling = hybridShapeFactory1.AddNewHybridScaling( _
            refTranslate, refTargetPoint, airfoilScales(i))
        hybridShapeScaling.VolumeResult = False
        hybridBody1.AppendHybridShape hybridShapeScaling

        ' 创建旋转变换
        Set hybridShapeRotate = hybridShapeFactory1.AddNewEmptyRotate()
        Set refScaling = part1.CreateReferenceFromObject(hybridShapeScaling)
        hybridShapeRotate.ElemToRotate = refScaling
        hybridShapeRotate.VolumeResult = False
        hybridShapeRotate.RotationType = 0

        Set refAxis = part1.CreateReferenceFromObject(hybridShapeLinePtDir1)
        hybridShapeRotate.Axis = refAxis
        hybridShapeRotate.AngleValue = airfoilTwists(i)
        hybridBody1.AppendHybridShape hybridShapeRotate

        hybridShapeRotate.Name = "Rotate." & (i + 1)

    Next

    ' 更新零件
    part1.Update

    ' 调整视图
    Set specsAndGeomWindow1 = CATIA.ActiveWindow
    Set viewer3D1 = specsAndGeomWindow1.ActiveViewer
    viewer3D1.Reframe

    MsgBox "参数化旋翼桨叶模型创建完成！"

End Sub

Sub CreateSimpleAirfoil(hSF, hybridBodyPoints, chordLength)
    ' 创建一个简化的翼型（NACA 0012 翼型作为示例）
    Dim points(9)

    points(0) = Array(0, 0, 0)
    points(1) = Array(chordLength * 0.1, chordLength * 0.012, 0)
    points(2) = Array(chordLength * 0.2, chordLength * 0.018, 0)
    points(3) = Array(chordLength * 0.3, chordLength * 0.021, 0)
    points(4) = Array(chordLength * 0.4, chordLength * 0.022, 0)
    points(5) = Array(chordLength * 0.5, chordLength * 0.021, 0)
    points(6) = Array(chordLength * 0.6, chordLength * 0.018, 0)
    points(7) = Array(chordLength * 0.8, chordLength * 0.012, 0)
    points(8) = Array(chordLength * 0.9, chordLength * 0.007, 0)
    points(9) = Array(chordLength * 1.0, 0, 0)

    Dim i
    For i = 0 To UBound(points)
        Set hybridShapePointCoord = hSF.AddNewPointCoord( _
            points(i)(0), points(i)(1), points(i)(2))
        hybridBodyPoints.AppendHybridShape hybridShapePointCoord
    Next

    ' 下表面点
    Dim lowerPoints(9)
    lowerPoints(0) = Array(0, 0, 0)
    lowerPoints(1) = Array(chordLength * 0.1, -chordLength * 0.012, 0)
    lowerPoints(2) = Array(chordLength * 0.2, -chordLength * 0.018, 0)
    lowerPoints(3) = Array(chordLength * 0.3, -chordLength * 0.021, 0)
    lowerPoints(4) = Array(chordLength * 0.4, -chordLength * 0.022, 0)
    lowerPoints(5) = Array(chordLength * 0.5, -chordLength * 0.021, 0)
    lowerPoints(6) = Array(chordLength * 0.6, -chordLength * 0.018, 0)
    lowerPoints(7) = Array(chordLength * 0.8, -chordLength * 0.012, 0)
    lowerPoints(8) = Array(chordLength * 0.9, -chordLength * 0.007, 0)
    lowerPoints(9) = Array(chordLength * 1.0, 0, 0)

    For i = UBound(lowerPoints) To 0 Step -1
        Set hybridShapePointCoord = hSF.AddNewPointCoord( _
            lowerPoints(i)(0), lowerPoints(i)(1), lowerPoints(i)(2))
        hybridBodyPoints.AppendHybridShape hybridShapePointCoord
    Next

End Sub
