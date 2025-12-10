import gradio as gr
import requests
import json
import os
from pathlib import Path
from loguru import logger
import time

# 导入find_free_port函数
from app.port_utils import find_free_port

# 配置日志
logger.add("frontend.log", rotation="500 MB")

# 修改：后端URL获取逻辑，适配挂载模式
def get_backend_url():
    # 在挂载模式下，使用相对路径调用后端API
    return "/api"  # 直接返回API前缀

# # 获取后端URL，优先从backend_port.txt文件读取端口
# def get_backend_url():
#     # 尝试从backend_port.txt文件读取端口
#     port_file = Path(__file__).parent.parent / "backend_port.txt"
#     if port_file.exists():
#         try:
#             port = int(port_file.read_text().strip())
#             return f"http://localhost:{port}"
#         except Exception:
#             pass
#     # 默认端口
#     return os.getenv("BACKEND_URL", "http://localhost:8000")

BACKEND_URL = get_backend_url()

def call_backend(job_title: str, requirements: str, top_n: int = 10) -> str:
    """调用后端API获取评分结果"""
    try:
        # 准备请求数据
        payload = {
            "job_title": job_title,
            "requirements": requirements,
            "top_n": top_n
        }
        
        # 修改：使用相对路径调用API
        api_url = f"{BACKEND_URL}/score"
        
        logger.info(f"发送请求到后端: {BACKEND_URL}/score")
        logger.info(f"请求数据: {payload}")
        
        # 发送POST请求到后端
        response = requests.post(
            f"{BACKEND_URL}/score",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=300  # 5分钟超时
        )
        
        logger.info(f"后端响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            # 后端返回的是{"results": [...]}，需要兼容列表或字符串等异常格式
            if isinstance(data, dict):
                results = data.get("results", [])
            elif isinstance(data, list):
                results = data
            else:
                error_msg = f"后端返回未知数据格式: {type(data)}"
                logger.error(error_msg)
                return f"<p style='color: red;'>错误: {error_msg}</p>"

            logger.info(f"收到 {len(results)} 个评分结果")
            
            # 构建展示用的HTML表格
            html = """
            <div style="font-family: Arial, sans-serif;">
                <h2 style="color: #333; margin-bottom: 12px;">候选人评分结果</h2>
                <div style="width: 100%; overflow-x: auto;">
                    <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; min-width: 960px; width: 100%; table-layout: fixed;">
                        <thead>
                            <tr style="background-color: #f2f2f2;">
                                <th style="text-align: left; width: 80px;">人才编号</th>
                                <th style="text-align: left; width: 80px;">得分</th>
                                <th style="text-align: left; width: 100px;">经验年限</th>
                                <th style="text-align: left; width: 200px;">核心技能</th>
                                <th style="text-align: left;">评分理由</th>
                            </tr>
                        </thead>
                        <tbody>
            """
            
            for idx, result in enumerate(results):
                # 解析结果
                # 人才编号使用原始ID（若缺失则退回序号）
                resume_index = result.get("original_id", result.get("resume_index", idx))
                summary_score = float(result.get("summary_score", result.get("rerank_score", 0) or 0))
                parsed_resume = result.get("parsed_resume", {}) or {}
                report = result.get("report", {}) or {}
                
                # 提取经验年限
                years_experience = parsed_resume.get("years_experience", "未知")
                
                # 提取核心技能（最多显示5个）
                skills = parsed_resume.get("skills", [])
                if isinstance(skills, str):
                    skills_list = [s.strip() for s in skills.split(",") if s.strip()]
                elif isinstance(skills, list):
                    skills_list = [str(s).strip() for s in skills if str(s).strip()]
                else:
                    skills_list = []
                core_skills = ", ".join(skills_list[:5]) if skills_list else "未知"
                
                # 提取评分理由
                ordered_scores = report.get("ordered_scores", [])
                reasoning = "无评分理由"
                if ordered_scores and isinstance(ordered_scores, list):
                    first_score = ordered_scores[0] if ordered_scores else {}
                    if isinstance(first_score, dict):
                        reasoning = first_score.get("reasoning", "无评分理由")
                
                # 格式化技能和理由，避免HTML问题
                core_skills = core_skills.replace("<", "&lt;").replace(">", "&gt;")
                reasoning = reasoning.replace("<", "&lt;").replace(">", "&gt;")
                
                html += f"""
                    <tr>
                        <td>{resume_index}</td>
                        <td>{summary_score:.2f}</td>
                        <td>{years_experience}</td>
                        <td>{core_skills}</td>
                        <td>{reasoning}</td>
                    </tr>
                """
            
            html += """
                        </tbody>
                    </table>
                </div>
            </div>
            """
            
            logger.info("成功生成结果表格")
            return html
        else:
            error_msg = f"后端返回错误: {response.status_code} - {response.text}"
            logger.error(error_msg)
            return f"<p style='color: red;'>错误: {error_msg}</p>"
            
    except Exception as e:
        error_msg = f"调用后端时发生异常: {str(e)}"
        logger.error(error_msg)
        return f"<p style='color: red;'>错误: {error_msg}</p>"

# 构建Gradio界面
# 构建Gradio界面
def build_demo():
    """构建Gradio演示界面"""
    with gr.Blocks(title="智能简历筛选系统", theme=gr.themes.Soft()) as demo:
        # 标题
        gr.Markdown("""
        # 📄 智能简历筛选系统
        **输入岗位名称和要求，系统将自动为您筛选最匹配的候选人。**
        """)
        
        # 第一行：两个卡片布局
        with gr.Row():
            # 卡片1：岗位基本信息和操作
            with gr.Column(scale=1, min_width=300):
                with gr.Group():
                    gr.Markdown("### 📋 岗位信息")
                    job_title = gr.Textbox(
                        label="岗位名称",
                        placeholder="例如：高级数据科学家",
                        value="高级数据科学家",
                        lines=1
                    )
                    with gr.Row():
                        top_n = gr.Slider(
                            minimum=1,
                            maximum=50,
                            value=10,
                            step=1,
                            label="返回候选人数量"
                        )
                    submit_btn = gr.Button(
                        "🚀 开始筛选", 
                        variant="primary",
                        size="lg",
                        scale=1
                    )
            
            # 卡片2：岗位要求
            with gr.Column(scale=2, min_width=500):
                with gr.Group():
                    gr.Markdown("### 📝 详细岗位要求")
                    requirements = gr.Textbox(
                        label="请详细描述岗位要求和职责",
                        placeholder="例如：\n1. 5年以上数据科学相关经验\n2. 精通Python和机器学习库\n3. 有深度学习项目经验\n4. 良好的沟通能力",
                        value="""岗位: 高级数据科学家
要求:
1. 5年以上数据科学相关经验
2. 精通Python和机器学习库
3. 有深度学习项目经验
4. 良好的沟通能力
5. 熟悉大数据处理技术
6. 有团队管理经验者优先""",
                        lines=12
                    )
        
        # 第二行：筛选结果展示
        with gr.Row():
            with gr.Column():
                gr.Markdown("### 📊 筛选结果")
                output = gr.HTML(
                    label="匹配候选人列表",
                    value="<div style='padding: 20px; text-align: center; color: #666;'>等待筛选结果...</div>"
                )
        
        # 第三行：使用说明和结果说明
        with gr.Row():
            # 左侧：使用说明
            with gr.Column(scale=1):
                with gr.Group():
                    gr.Markdown("### 📖 使用说明")
                    gr.Markdown("""
                    **第一步**：填写岗位名称
                    - 例如：高级数据科学家、前端开发工程师等
                    
                    **第二步**：设置筛选数量
                    - 滑动选择需要返回的候选人数量
                    - 范围：1-50人
                    
                    **第三步**：详细描述岗位要求
                    - 列出具体的技能要求
                    - 描述工作职责
                    - 说明经验要求
                    
                    **第四步**：开始筛选
                    - 点击"开始筛选"按钮
                    - 系统将自动匹配最佳候选人
                    """)
            
            # 右侧：结果说明
            with gr.Column(scale=1):
                with gr.Group():
                    gr.Markdown("### 📈 结果解读")
                    gr.Markdown("""
                    **人才编号**
                    - 候选人在人才库中的唯一标识符
                    - 可用于后续联系和跟进
                    
                    **综合得分**
                    - 得分越高表示匹配度越高
                    - 基于大模型综合评估生成
                    
                    **工作经验**
                    - 候选人的相关工作经验年限
                    - 自动从简历中提取
                    
                    **核心技能匹配**
                    - 候选人具备的核心技能
                    - 重点展示与岗位相关的技能
                    
                    **评分理由**
                    - 系统生成的评估依据
                    - 解释候选人得分的具体原因
                    """)
        
        # 页脚信息
        gr.Markdown("---")
        with gr.Row():
            gr.Markdown(
                """
                <div style="text-align: center; color: #999; font-size: 12px;">
                    智能简历筛选系统 | 基于AI的智能人才匹配 | 数据实时更新
                </div>
                """,
                elem_id="footer"
            )
        
        # 设置按钮点击事件
        submit_btn.click(
            fn=call_backend,
            inputs=[job_title, requirements, top_n],
            outputs=output
        )
    
    return demo

# # 运行函数
# def run():
#     port_start = 6060
#     port = find_free_port(port_start)
#     # 修正端口文件写入路径，确保在项目根目录下创建文件
#     port_file_path = Path(__file__).parent.parent / "frontend_port.txt"
#     port_file_path.write_text(str(port), encoding="utf-8")
#     print(f"[前端] 运行在 http://127.0.0.1:{port}")
#     demo = build_demo()
#     demo.launch(server_name="0.0.0.0", server_port=port, show_api=False, share=False)

# if __name__ == "__main__":
#     run()
