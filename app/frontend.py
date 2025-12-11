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

# 修改：后端URL获取逻辑，适配Render平台
def get_backend_url():
    # 检查是否在Render环境
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if render_url:
        # 在Render平台上，返回基础URL（不带/api）
        return render_url.rstrip('/')  # 确保没有末尾斜杠
    else:
        # 本地开发环境或其他环境
        port_file = Path(__file__).parent.parent / "backend_port.txt"
        if port_file.exists():
            try:
                port = int(port_file.read_text().strip())
                return f"http://localhost:{port}"
            except Exception:
                pass
        # 默认端口
        return os.getenv("BACKEND_URL", "http://localhost:8000")

BACKEND_URL = get_backend_url()

# 预设岗位模板
JOB_TEMPLATES = {
    "": "请选择或输入自定义岗位...",
    "高级数据科学家": """岗位: 高级数据科学家
要求:
1. 5年以上数据科学相关经验
2. 精通Python和机器学习库（如scikit-learn, TensorFlow, PyTorch）
3. 有深度学习项目经验，熟悉CNN、RNN等模型
4. 良好的沟通能力和团队协作精神
5. 熟悉大数据处理技术（如Spark, Hadoop）
6. 有团队管理经验者优先""",
    "产品经理": """岗位: 产品经理
要求:
1. 3年以上产品管理经验，有成功产品案例
2. 熟悉产品生命周期管理，能独立负责产品规划
3. 具备良好的市场洞察力和用户需求分析能力
4. 熟练使用Axure、Figma等原型设计工具
5. 具备优秀的沟通协调能力，能有效推动跨部门合作
6. 有互联网或科技行业背景优先""",
    "前端工程师": """岗位: 前端工程师
要求:
1. 3年以上前端开发经验，精通Vue.js或React框架
2. 熟练掌握HTML5、CSS3、JavaScript(ES6+)
3. 有响应式设计和移动端开发经验
4. 熟悉Webpack等构建工具和npm生态系统
5. 了解前端性能优化和浏览器兼容性处理
6. 有良好的代码规范意识和团队协作能力"""
}

def update_requirements(job_title):
    """根据选择的岗位模板更新岗位要求"""
    return JOB_TEMPLATES.get(job_title, "")

def call_backend(job_title: str, requirements: str, top_n: int = 10) -> str:
    """调用后端API获取评分结果"""
    try:
        # 准备请求数据
        payload = {
            "job_title": job_title,
            "requirements": requirements,
            "top_n": top_n
        }
        
        # 构造完整的API URL
        api_url = f"{BACKEND_URL}/api/score"
        
        logger.info(f"发送请求到后端: {api_url}")
        logger.info(f"请求数据: {payload}")
        
        # 发送POST请求到后端
        response = requests.post(
            api_url,
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
            
            # 检查是否有结果
            if not results:
                return """
                <div style="text-align: center; padding: 40px; color: #666;">
                    <h3>🔍 未找到匹配的候选人</h3>
                    <p>请尝试调整岗位要求或增加候选人数量</p>
                </div>
                """
            
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
                                <th style="text-align: left; width: 120px;">操作</th>
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
                        <td>
                            <button style="margin-right: 5px; padding: 2px 6px; font-size: 12px;">查看详情</button>
                            <button style="padding: 2px 6px; font-size: 12px;">标记</button>
                        </td>
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
def build_demo():
    """构建Gradio演示界面"""
    with gr.Blocks(title="智能简历筛选系统", theme=gr.themes.Soft()) as demo:
        # 标题（增大字号并加重字重）
        gr.Markdown("""
        # <span style="font-size: 24px; font-weight: 600;">📄 智能简历筛选系统</span>
        **<span style="font-size: 16px;">输入岗位名称和要求，系统将自动为您筛选最匹配的候选人。</span>**
        """)
        
        # 第一行：两个卡片并列布局（添加浅色背景卡片样式）
        with gr.Row():
            # 卡片1：岗位基本信息和操作（左侧）
            with gr.Column(scale=1):
                with gr.Group(elem_classes=["job-card"]):
                    gr.Markdown("### 📋 岗位信息", elem_classes=["card-title"])
                    job_title = gr.Textbox(
                        label="岗位名称",
                        placeholder="例如：高级数据科学家",
                        value="高级数据科学家",
                        lines=1
                    )
                    
                    # 添加预设岗位模板下拉菜单
                    template_dropdown = gr.Dropdown(
                        choices=list(JOB_TEMPLATES.keys()),
                        label="从常用岗位中选择",
                        value=""
                    )
                    
                    with gr.Row():
                        top_n = gr.Slider(
                            minimum=1,
                            maximum=50,
                            value=10,
                            step=1,
                            label="返回候选人数量"
                        )
                        # 添加数字显示
                        top_n_number = gr.Number(value=10, label="", precision=0, interactive=False, 
                                                elem_classes=["slider-number"])
                    
                    submit_btn = gr.Button(
                        "🚀 开始筛选", 
                        variant="primary",
                        size="lg",
                        elem_classes=["submit-btn"]
                    )
            
            # 卡片2：岗位要求（右侧）（改为可编辑的文本域）
            with gr.Column(scale=2):
                with gr.Group(elem_classes=["requirements-card"]):
                    gr.Markdown("### 📝 详细岗位要求", elem_classes=["card-title"])
                    requirements = gr.TextArea(
                        label="请在此输入或编辑岗位要求：",
                        placeholder="请在此输入或编辑岗位要求...",
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
        
        # 第二行：筛选结果展示（添加空状态设计）
        with gr.Row():
            with gr.Column():
                gr.Markdown("### 📊 筛选结果", elem_classes=["section-title"])
                output = gr.HTML(
                    label="匹配候选人列表",
                    value="<div style='padding: 40px; text-align: center; color: #666;'><h3>📋 暂无筛选结果，请填写岗位信息并开始筛选。</h3><p>填写岗位信息后，点击\"开始筛选\"按钮获取匹配结果</p></div>",
                    elem_classes=["results-container"]
                )
        
        # 第三行：使用说明和结果说明（字体缩小为原来的一半，添加图标）
        with gr.Row():
            # 左侧：使用说明
            with gr.Column(scale=1):
                with gr.Group(elem_classes=["instructions-card"]):
                    gr.Markdown("### 📖 使用说明", elem_classes=["card-title"])
                    gr.Markdown("""
                    <div style="font-size: 12px; line-height: 1.6;">
                    <strong>1. 填写岗位信息</strong>
                    <ul>
                        <li>输入岗位名称或从预设模板中选择</li>
                        <li>设置需要返回的候选人数量</li>
                    </ul>
                    
                    <strong>2. 编辑岗位要求</strong>
                    <ul>
                        <li>详细描述岗位技能要求</li>
                        <li>列出工作职责和经验要求</li>
                    </ul>
                    
                    <strong>3. 开始筛选</strong>
                    <ul>
                        <li>点击"开始筛选"按钮</li>
                        <li>系统将智能分析并匹配候选人</li>
                    </ul>
                    </div>
                    """)
            
            # 右侧：结果说明
            with gr.Column(scale=1):
                with gr.Group(elem_classes=["interpretation-card"]):
                    gr.Markdown("### 📈 结果解读", elem_classes=["card-title"])
                    gr.Markdown("""
                    <div style="font-size: 12px; line-height: 1.6;">
                    <strong>人才编号</strong>
                    <ul>
                        <li>候选人在人才库中的唯一标识符</li>
                        <li>可用于后续联系和跟进</li>
                    </ul>
                    
                    <strong>综合得分</strong>
                    <ul>
                        <li>得分越高表示匹配度越高</li>
                        <li>基于大模型综合评估生成</li>
                    </ul>
                    
                    <strong>工作经验</strong>
                    <ul>
                        <li>候选人的相关工作经验年限</li>
                        <li>自动从简历中提取</li>
                    </ul>
                    
                    <strong>核心技能匹配</strong>
                    <ul>
                        <li>候选人具备的核心技能</li>
                        <li>重点展示与岗位相关的技能</li>
                    </ul>
                    
                    <strong>评分理由</strong>
                    <ul>
                        <li>系统生成的评估依据</li>
                        <li>解释候选人得分的具体原因</li>
                    </ul>
                    </div>
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
        
        # 绑定事件
        # 滑块与数字显示联动
        top_n.change(fn=lambda x: x, inputs=top_n, outputs=top_n_number)
        
        # 预设模板下拉菜单事件
        template_dropdown.change(
            fn=update_requirements,
            inputs=template_dropdown,
            outputs=requirements
        )
        
        # 设置按钮点击事件
        submit_btn.click(
            fn=lambda *args: "<div style='padding: 20px; text-align: center;'><h3>🤖 正在智能分析简历，请稍候…</h3><p>这可能需要一些时间，请耐心等待</p></div>",
            inputs=[],
            outputs=output
        ).then(
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