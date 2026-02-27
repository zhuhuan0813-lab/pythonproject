from pycatia import catia
import os
import time
from datetime import datetime


def complete_verification_modify(file_path, param_name="翼尖弦长", new_value=1200.0):
    """
    完整验证脚本：修改参数并进行全方位验证
    """

    # ============================================
    # 第1步：打开文件并获取对象
    # ============================================
    print("=" * 70)
    print("第1步：正在打开CATIA文件")
    print("=" * 70)

    caa = catia()
    documents = caa.documents
    doc = documents.open(file_path)

    if file_path.endswith('.CATPart'):
        obj = doc.part
        file_type = "零件"
    elif file_path.endswith('.CATProduct'):
        obj = doc.product
        file_type = "装配体"
    else:
        raise ValueError("不支持的文件类型")

    print(f"✓ 文件类型: {file_type}")
    print(f"✓ 文件路径: {file_path}")

    parameters = obj.parameters

    # ============================================
    # 第2步：记录修改前的状态
    # ============================================
    print("\n" + "=" * 70)
    print("第2步：记录修改前的状态")
    print("=" * 70)

    # 2.1 记录目标参数
    try:
        param = parameters.item(param_name)
        old_value = param.value
        param_type = type(param).__name__
        print(f"\n【目标参数】")
        print(f"  参数名: {param_name}")
        print(f"  当前值: {old_value}")
        print(f"  类型: {param_type}")
    except Exception as e:
        print(f"\n✗ 错误：找不到参数 '{param_name}': {e}")
        return None

    # 2.2 记录相关参数
    related_params = [
        "翼根弦长",
        "翼中弦长",
        "翼尖弦长",
        "旋翼直径",
        "翼根扭转角",
        "翼中扭转角",
        "翼尖扭转角"
    ]

    print(f"\n【相关参数 - 修改前】")
    before_state = {}
    for pname in related_params:
        try:
            p = parameters.item(pname)
            val = p.value
            before_state[pname] = val
            print(f"  {pname}: {val}")
        except:
            before_state[pname] = None

    # 2.3 记录几何属性（仅对零件）
    before_geometry = {}
    if file_type == "零件":
        print(f"\n【几何属性 - 修改前】")
        try:
            obj.update()
            bodies = obj.bodies
            if bodies.count > 0:
                body = bodies.item(1)
                measurable = obj.get_measurable(body)

                try:
                    volume = measurable.volume
                    before_geometry['体积'] = volume
                    print(f"  体积: {volume:.2f} mm³")
                except:
                    print(f"  体积: 无法获取")

                try:
                    area = measurable.area
                    before_geometry['表面积'] = area
                    print(f"  表面积: {area:.2f} mm²")
                except:
                    print(f"  表面积: 无法获取")
        except Exception as e:
            print(f"  几何属性获取失败: {e}")

    # 2.4 导出修改前的STEP文件
    output_dir = os.path.join(os.path.dirname(file_path), "验证对比")
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"\n【导出修改前的STEP文件】")
    before_step = os.path.join(output_dir, f"before_翼尖弦长_{timestamp}.stp")
    try:
        doc.export_data(before_step, "stp")
        before_step_size = os.path.getsize(before_step)
        print(f"  ✓ 已导出: {before_step}")
        print(f"  ✓ 文件大小: {before_step_size / 1024:.2f} KB")
    except Exception as e:
        print(f"  ✗ 导出失败: {e}")
        before_step = None
        before_step_size = 0

    # ============================================
    # 第3步：修改参数
    # ============================================
    print("\n" + "=" * 70)
    print("第3步：修改参数")
    print("=" * 70)

    print(f"\n正在将 '{param_name}' 从 {old_value} 改为 {new_value}...")
    param.value = new_value
    print(f"✓ 参数值已设置为: {param.value}")

    # ============================================
    # 第4步：更新模型
    # ============================================
    print("\n" + "=" * 70)
    print("第4步：更新模型（这可能需要几秒钟）")
    print("=" * 70)

    print("\n正在调用 obj.update()...")
    start_time = time.time()
    obj.update()
    update_time = time.time() - start_time
    print(f"✓ 更新完成，耗时: {update_time:.2f} 秒")

    # 等待CATIA完全刷新
    print("等待CATIA刷新界面...")
    time.sleep(2)

    # ============================================
    # 第5步：验证修改后的状态
    # ============================================
    print("\n" + "=" * 70)
    print("第5步：验证修改后的状态")
    print("=" * 70)

    # 5.1 验证目标参数
    param = parameters.item(param_name)
    current_value = param.value
    print(f"\n【目标参数 - 修改后】")
    print(f"  {param_name}: {current_value}")

    if abs(current_value - new_value) < 0.001:
        print(f"  ✓ 参数修改成功")
    else:
        print(f"  ✗ 警告：参数值不符合预期")

    # 5.2 验证相关参数
    print(f"\n【相关参数 - 修改后】")
    after_state = {}
    for pname in related_params:
        try:
            p = parameters.item(pname)
            val = p.value
            after_state[pname] = val
            print(f"  {pname}: {val}")
        except:
            after_state[pname] = None

    # 5.3 验证几何属性
    after_geometry = {}
    if file_type == "零件":
        print(f"\n【几何属性 - 修改后】")
        try:
            obj.update()
            bodies = obj.bodies
            if bodies.count > 0:
                body = bodies.item(1)
                measurable = obj.get_measurable(body)

                try:
                    volume = measurable.volume
                    after_geometry['体积'] = volume
                    print(f"  体积: {volume:.2f} mm³")
                except:
                    print(f"  体积: 无法获取")

                try:
                    area = measurable.area
                    after_geometry['表面积'] = area
                    print(f"  表面积: {area:.2f} mm²")
                except:
                    print(f"  表面积: 无法获取")
        except Exception as e:
            print(f"  几何属性获取失败: {e}")

    # 5.4 导出修改后的STEP文件
    print(f"\n【导出修改后的STEP文件】")
    after_step = os.path.join(output_dir, f"after_翼尖弦长_{timestamp}.stp")
    try:
        doc.export_data(after_step, "stp")
        after_step_size = os.path.getsize(after_step)
        print(f"  ✓ 已导出: {after_step}")
        print(f"  ✓ 文件大小: {after_step_size / 1024:.2f} KB")
    except Exception as e:
        print(f"  ✗ 导出失败: {e}")
        after_step = None
        after_step_size = 0

    # ============================================
    # 第6步：对比分析
    # ============================================
    print("\n" + "=" * 70)
    print("第6步：对比分析")
    print("=" * 70)

    has_changes = False

    # 6.1 参数变化
    print(f"\n【参数变化对比】")
    for pname in related_params:
        before_val = before_state.get(pname)
        after_val = after_state.get(pname)

        if before_val is not None and after_val is not None:
            diff = after_val - before_val
            if abs(diff) > 0.0001:
                has_changes = True
                diff_percent = (diff / before_val * 100) if before_val != 0 else 0
                print(f"  {pname}:")
                print(f"    修改前: {before_val:.4f}")
                print(f"    修改后: {after_val:.4f}")
                print(f"    变化量: {diff:+.4f} ({diff_percent:+.2f}%)")

    # 6.2 几何变化
    if file_type == "零件" and before_geometry and after_geometry:
        print(f"\n【几何属性变化】")
        for attr in ['体积', '表面积']:
            before_val = before_geometry.get(attr)
            after_val = after_geometry.get(attr)

            if before_val is not None and after_val is not None:
                diff = after_val - before_val
                if abs(diff) > 0.01:
                    has_changes = True
                    diff_percent = (diff / before_val * 100) if before_val != 0 else 0
                    print(f"  {attr}:")
                    print(f"    修改前: {before_val:.2f}")
                    print(f"    修改后: {after_val:.2f}")
                    print(f"    变化量: {diff:+.2f} ({diff_percent:+.2f}%)")

    # 6.3 文件大小变化
    if before_step and after_step:
        print(f"\n【STEP文件大小变化】")
        size_diff = after_step_size - before_step_size
        size_diff_percent = (size_diff / before_step_size * 100) if before_step_size != 0 else 0
        print(f"  修改前: {before_step_size / 1024:.2f} KB")
        print(f"  修改后: {after_step_size / 1024:.2f} KB")
        print(f"  变化量: {size_diff / 1024:+.2f} KB ({size_diff_percent:+.2f}%)")

        if abs(size_diff_percent) > 1:
            has_changes = True

    # ============================================
    # 第7步：验证结论
    # ============================================
    print("\n" + "=" * 70)
    print("第7步：验证结论")
    print("=" * 70)

    if has_changes:
        print("\n✅ 结论：模型已真实更新！")
        print("   检测到明显的几何或参数变化")
    else:
        print("\n⚠️  警告：未检测到明显变化")
        print("   可能原因：")
        print("   1. 参数未关联到几何")
        print("   2. 需要更新其他关联参数")
        print("   3. 模型可能有约束冲突")

    # ============================================
    # 第8步：用户目视检查
    # ============================================
    print("\n" + "=" * 70)
    print("第8步：用户目视检查（最重要！）")
    print("=" * 70)

    print("\n⚠️  请立即切换到CATIA窗口进行目视检查！")
    print("\n检查清单：")
    print(f"  □ 桨叶翼尖部分是否明显变宽？")
    print(
        f"     (从 {old_value:.2f} mm → {new_value:.2f} mm, 变化 {((new_value - old_value) / old_value * 100):+.1f}%)")
    print(f"  □ 整体桨叶形状是否合理？")
    print(f"  □ 翼尖部分是否比翼根还宽了？(这可能不合理！)")
    print(f"  □ 是否有红色错误标记或几何异常？")
    print(f"  □ 参数树中 '{param_name}' 是否显示为 {new_value} mm？")

    if before_step and after_step:
        print(f"\n导出的STEP文件位置：")
        print(f"  修改前: {before_step}")
        print(f"  修改后: {after_step}")
        print(f"  (可用其他CAD软件打开对比)")

    print("\n" + "=" * 70)
    input("检查完成后，按回车键继续...")

    # ============================================
    # 第9步：保存决策
    # ============================================
    print("\n" + "=" * 70)
    print("第9步：保存决策")
    print("=" * 70)

    print(f"\n当前修改：")
    print(f"  {param_name}: {old_value} → {current_value}")
    print(f"  文件: {os.path.basename(file_path)}")

    # 特别警告
    if param_name == "翼尖弦长" and new_value > before_state.get("翼根弦长", 0):
        print("\n⚠️  警告：翼尖弦长({}) 现在大于翼根弦长({})".format(
            new_value, before_state.get("翼根弦长", 0)))
        print("   这在气动设计上通常是不合理的！")
        print("   请确认这是您想要的设计。")

    save_choice = input("\n模型看起来正确吗？是否保存修改? (y/n): ")

    if save_choice.lower() == 'y':
        try:
            doc.save()
            print("✅ 文件已保存")
            print(f"   保存位置: {file_path}")
        except Exception as e:
            print(f"✗ 保存失败: {e}")
    else:
        print("❌ 未保存文件")
        print("   修改将在关闭文件后丢失")

    # ============================================
    # 第10步：生成报告
    # ============================================
    print("\n" + "=" * 70)
    print("第10步：生成验证报告")
    print("=" * 70)

    report_path = os.path.join(output_dir, f"验证报告_翼尖弦长_{timestamp}.txt")
    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write("CATIA参数修改验证报告\n")
            f.write("=" * 70 + "\n\n")

            f.write(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"文件: {file_path}\n")
            f.write(f"文件类型: {file_type}\n\n")

            f.write("-" * 70 + "\n")
            f.write("修改内容\n")
            f.write("-" * 70 + "\n")
            f.write(f"参数名: {param_name}\n")
            f.write(f"修改前: {old_value}\n")
            f.write(f"修改后: {current_value}\n")
            f.write(f"变化量: {current_value - old_value:+.4f}\n")
            f.write(f"变化率: {((current_value - old_value) / old_value * 100):+.2f}%\n\n")

            f.write("-" * 70 + "\n")
            f.write("相关参数变化\n")
            f.write("-" * 70 + "\n")
            for pname in related_params:
                before_val = before_state.get(pname)
                after_val = after_state.get(pname)
                if before_val is not None and after_val is not None:
                    diff = after_val - before_val
                    f.write(f"{pname}:\n")
                    f.write(f"  修改前: {before_val:.4f}\n")
                    f.write(f"  修改后: {after_val:.4f}\n")
                    f.write(f"  变化: {diff:+.4f}\n\n")

            if before_geometry and after_geometry:
                f.write("-" * 70 + "\n")
                f.write("几何属性变化\n")
                f.write("-" * 70 + "\n")
                for attr in ['体积', '表面积']:
                    before_val = before_geometry.get(attr)
                    after_val = after_geometry.get(attr)
                    if before_val is not None and after_val is not None:
                        diff = after_val - before_val
                        diff_percent = (diff / before_val * 100) if before_val != 0 else 0
                        f.write(f"{attr}:\n")
                        f.write(f"  修改前: {before_val:.2f}\n")
                        f.write(f"  修改后: {after_val:.2f}\n")
                        f.write(f"  变化: {diff:+.2f} ({diff_percent:+.2f}%)\n\n")

            f.write("-" * 70 + "\n")
            f.write("导出文件\n")
            f.write("-" * 70 + "\n")
            if before_step:
                f.write(f"修改前STEP: {before_step}\n")
            if after_step:
                f.write(f"修改后STEP: {after_step}\n")

            f.write("\n" + "=" * 70 + "\n")
            f.write("验证结论: " + ("模型已真实更新" if has_changes else "未检测到明显变化") + "\n")
            f.write("=" * 70 + "\n")

        print(f"✓ 验证报告已保存: {report_path}")
    except Exception as e:
        print(f"✗ 报告生成失败: {e}")

    print("\n" + "=" * 70)
    print("验证流程完成！")
    print("=" * 70)

    return {
        'old_value': old_value,
        'new_value': current_value,
        'before_state': before_state,
        'after_state': after_state,
        'before_geometry': before_geometry,
        'after_geometry': after_geometry,
        'has_changes': has_changes,
        'report_path': report_path
    }


if __name__ == "__main__":
    # ============================================
    # 配置区域
    # ============================================
    file_path = r"D:\17484\Documents\OneDrive\Desktop\XV-15桨叶总成\XV-15 ASM.CATProduct"

    # 执行完整验证
    result = complete_verification_modify(
        file_path=file_path,
        param_name="翼尖弦长",
        new_value=1200.0
    )

    if result:
        print("\n" + "=" * 70)
        print("快速摘要")
        print("=" * 70)
        print(f"修改: {result['old_value']} → {result['new_value']}")
        print(f"模型是否更新: {'是' if result['has_changes'] else '否'}")
        print(f"报告位置: {result['report_path']}")