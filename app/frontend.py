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

# 获取后端URL
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

def call_backend(job_title: str, requirements: str, top_n: int = 10) -> str:
    """调用后端API获取评分结果"""
    try:
        # 准备请求数据
        payload = {
            "job_title": job_title,
            "requirements": requirements,
            "top_n": top_n
        }
        
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
            results = response.json()
            logger.info(f"收到 {len(results)} 个评分结果")
            
            # 构建展示用的HTML表格
            html = """
            <div style="font-family: Arial, sans-serif;">
                <h2 style="color: #333;">候选人评分结果</h2>
                <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
                    <thead>
                        <tr style="background-color: #f2f2f2;">
                            <th style="text-align: left;">人才编号</th>
                            <th style="text-align: left;">原始ID</th>
                            <th style="text-align: left;">得分</th>
                            <th style="text-align: left;">经验年限</th>
                            <th style="text-align: left;">核心技能</th>
                            <th style="text-align: left;">评分理由</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            
            for idx, result in enumerate(results):
                # 解析结果
                resume_index = result.get("resume_index", idx)
                original_id = result.get("original_id", "未知")
                summary_score = result.get("summary_score", 0)
                parsed_resume = result.get("parsed_resume", {})
                report = result.get("report", {})
                
                # 提取经验年限
                years_experience = parsed_resume.get("years_experience", "未知")
                
                # 提取核心技能（最多显示5个）
                skills = parsed_resume.get("skills", [])
                if isinstance(skills, list):
                    core_skills = ", ".join(skills[:5])
                else:
                    core_skills = str(skills)[:50]  # 限制长度
                
                # 提取评分理由
                ordered_scores = report.get("ordered_scores", [])
                if ordered_scores:
                    reasoning = ordered_scores[0].get("reasoning", "无评分理由")
                else:
                    reasoning = "无评分理由"
                
                # 格式化技能和理由，避免HTML问题
                core_skills = core_skills.replace("<", "&lt;").replace(">", "&gt;")
                reasoning = reasoning.replace("<", "&lt;").replace(">", "&gt;")
                
                html += f"""
                    <tr>
                        <td>{resume_index}</td>
                        <td>{original_id}</td>
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
def build_demo():
    """构建Gradio演示界面"""
    with gr.Blocks(title="智能简历筛选系统") as demo:
        gr.Markdown("# 智能简历筛选系统")
        gr.Markdown("输入岗位名称和要求，系统将自动为您筛选最匹配的候选人。")
        
        with gr.Row():
            with gr.Column(scale=1):
                job_title = gr.Textbox(
                    label="岗位名称",
                    placeholder="例如：高级数据科学家",
                    value="高级数据科学家"
                )
                requirements = gr.Textbox(
                    label="岗位要求",
                    placeholder="请输入详细的岗位要求...",
                    value="""岗位: 高级数据科学家
要求:
1. 5年以上数据科学相关经验
2. 精通Python和机器学习库
3. 有深度学习项目经验
4. 良好的沟通能力""",
                    lines=10
                )
                top_n = gr.Slider(
                    minimum=1,
                    maximum=50,
                    value=10,
                    step=1,
                    label="返回候选人数量"
                )
                submit_btn = gr.Button("开始筛选", variant="primary")
            
            with gr.Column(scale=2):
                output = gr.HTML(label="筛选结果")
        
        # 设置按钮点击事件
        submit_btn.click(
            fn=call_backend,
            inputs=[job_title, requirements, top_n],
            outputs=output
        )
        
        # 添加说明文字
        gr.Markdown("""
        ### 使用说明
        1. 输入岗位名称和详细要求
        2. 选择需要返回的候选人数量
        3. 点击"开始筛选"按钮
        4. 等待系统处理并查看结果
        
        ### 结果说明
        - **人才编号**: 候选人在人才库中的唯一标识符
        - **得分**: 候选人的综合评分
        - **经验(年)**: 候选人的工作经验年限
        - **核心技能**: 候选人在岗位要求中提及的主要技能
        - **评分理由**: 系统根据岗位要求和候选人简历生成的评分理由
        """)
    
    return demo

# 运行函数
def run():
    port_start = 6060
    port = find_free_port(port_start)
    # 修正端口文件写入路径，确保在项目根目录下创建文件
    port_file_path = Path(__file__).parent.parent / "frontend_port.txt"
    port_file_path.write_text(str(port), encoding="utf-8")
    print(f"[前端] 运行在 http://127.0.0.1:{port}")
    demo = build_demo()
    demo.launch(server_name="0.0.0.0", server_port=port, show_api=False, share=False)

if __name__ == "__main__":
    run()