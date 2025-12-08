import warnings
from plistlib import loads

import pandas as pd
from typing import List, Dict, Optional, Any
import os

from dotenv import load_dotenv
from langchain_classic.retrievers import EnsembleRetriever, ContextualCompressionRetriever
from langchain_classic.retrievers.document_compressors import LLMChainExtractor
from langchain_community.vectorstores import FAISS
from llama_index.core.indices import vector_store

load_dotenv()

# LlamaIndex相关导入
from llama_index.core import Document, Settings
from llama_index.core.node_parser import SentenceSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from openai import OpenAI
from langchain_community.retrievers import BM25Retriever

# 混合检索相关导入
from llama_index.core.retrievers import QueryFusionRetriever
from llama_index.core.schema import NodeWithScore, TextNode

# 交叉编码器相关导入
from sentence_transformers import CrossEncoder
import numpy as np

# 忽略一些警告
warnings.filterwarnings("ignore")



class SimpleRAG:
    #初始化
    def __init__(self, csv_file_path: str, top_n: int = 20):
        """
        初始化简化的RAG系统（完全使用LangChain）
        """
        self.csv_file_path = csv_file_path
        self.top_n = top_n
        self.documents = []
        self.retriever = None
        self.cross_encoder = None

        # 获取API配置
        self.api_key = os.getenv("OPENAI_API_KEY") or os.getenv("Gemini_Api_Key")
        self.base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("Gemini_Base_Url")
        self.model_name = os.getenv("OPENAI_MODEL") or os.getenv("Gemini_Model_Name") or "gpt-3.5-turbo"

        if not self.api_key:
            print("警告: 未找到API Key，将使用本地模型")
            print("请设置 OPENAI_API_KEY 环境变量或通过 .env 文件设置")
            print("示例: OPENAI_API_KEY=sk-your-key-here")

        # 初始化组件
        self._init_components()
        self._load_data()
        self._build_retriever()
    def _init_components(self):
        """初始化必要的组件"""
        try:
            # 初始化LLM
            llm_kwargs = {
                "temperature": 0.1,
                "model_name": self.model_name
            }

            if self.api_key:
                llm_kwargs["openai_api_key"] = self.api_key
                if self.base_url:
                    llm_kwargs["openai_api_base"] = self.base_url

            self.llm = ChatOpenAI(**llm_kwargs)

            # 初始化嵌入模型
            embedding_kwargs = {
                "model":os.getenv("EMBEDDING_MODEL_NAME")
            }

            if self.api_key:
                embedding_kwargs["openai_api_key"] = self.api_key
                if self.base_url:
                    embedding_kwargs["openai_api_base"] = self.base_url

            self.embeddings = OpenAIEmbeddings(**embedding_kwargs)

            # 尝试初始化交叉编码器（可选）
            try:
                self.cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
                print("交叉编码器初始化成功")
            except Exception as e:
                print(f"交叉编码器初始化失败，将不使用重排序: {e}")
                self.cross_encoder = None

        except Exception as e:
            print(f"初始化组件失败: {e}")
            raise
    #从csv数据中加载
    def _load_data(self):
        """加载CSV数据 - 按行进行chunk和embedding"""
        print(f"正在加载数据: {self.csv_file_path}")

        try:
            # 读取CSV文件
            df = pd.read_csv(self.csv_file_path)
            print(f"成功读取 {len(df)} 行数据（每个人对应一行）")

            # 转换为文档格式 - 每行对应一个文档
            from langchain_core.documents import Document

            documents = []
            for idx, row in df.iterrows():
                # 创建文档内容 - 每个人的完整信息
                content = f"Category: {row.get('Category', 'Unknown')}\n\n"
                content += f"Resume: {row.get('Resume', 'No resume information')}"

                # 如果有其他列，也添加到内容中
                for col in df.columns:
                    if col not in ['Category', 'Resume'] and col in row:
                        content += f"\n{col}: {row[col]}"

                # 创建文档对象 - 每个人对应一个独立的文档
                doc = Document(
                    page_content=content,
                    metadata={
                        "id": idx,
                        "category": row.get('Category', 'Unknown'),
                        "row_index": idx,
                        "person_id": idx,  # 明确标识这是一个人
                        "chunk_type": "person"  # 标识chunk类型为个人
                    }
                )
                documents.append(doc)
                
                # 打印每个文档的信息
                if idx < 5:  # 只打印前5个作为示例
                    print(f"文档 {idx}: 类别={row.get('Category', 'Unknown')}, 内容长度={len(content)}")

            self.documents = documents
            print(f"成功创建 {len(self.documents)} 个文档（每个人对应一个文档）")
            print(f"文档元数据示例: {documents[0].metadata if documents else '无文档'}")

        except Exception as e:
            print(f"加载数据失败: {e}")
            raise
    #建好检索器
    def _build_retriever(self):
        """构建检索器 - 按行进行embedding"""
        print("正在构建检索器...")

        try:
            if not self.documents:
                raise ValueError("没有加载文档数据")

            print(f"文档数量: {len(self.documents)}")
            print(f"第一个文档内容预览: {self.documents[0].page_content[:200]}...")
            print(f"第一个文档元数据: {self.documents[0].metadata}")

            # 1. 构建向量检索器 - 每个文档独立embedding
            print("正在构建向量索引（按行embedding）...")
            vectorstore = FAISS.from_documents(
                documents=self.documents,
                embedding=self.embeddings
            )
            vector_retriever = vectorstore.as_retriever(
                search_kwargs={"k": min(8, len(self.documents))}
            )
            print("向量索引构建完成")

            # 2. 构建BM25检索器 - 每个文档独立索引
            print("正在构建BM25检索器（按行索引）...")
            bm25_retriever = BM25Retriever.from_documents(
                self.documents
            )
            bm25_retriever.k = min(8, len(self.documents))
            print("BM25检索器构建完成")

            # 3. 组合检索器
            self.retriever = EnsembleRetriever(
                retrievers=[vector_retriever, bm25_retriever],
                weights=[0.5, 0.5]
            )

            print("混合检索器构建完成")
            print(f"检索器配置: 向量检索器k={min(8, len(self.documents))}, BM25检索器k={min(8, len(self.documents))}")

        except Exception as e:
            print(f"构建检索器失败: {e}")
            # 回退到BM25
            self.retriever = BM25Retriever.from_documents(self.documents)
            self.retriever.k = min(8, len(self.documents))
            print("回退到BM25检索器")
    #用cross encoder对结果精排序
    def _rerank_results(self, query: str, documents: List[Dict], top_k: int = 5) -> List[Dict]:
        """使用交叉编码器重排序结果"""
        if not self.cross_encoder or len(documents) <= 1:
            return documents[:top_k]

        try:
            print(f"使用交叉编码器对 {len(documents)} 个结果进行重排序...")

            # 准备输入
            pairs = [(query, doc["content"][:500]) for doc in documents]  # 限制文本长度

            # 计算分数
            scores = self.cross_encoder.predict(pairs)

            # 打印重排序前的分数
            print("\n=== 重排序前分数 ===")
            for i, (doc, score) in enumerate(zip(documents, scores)):
                print(f"文档 {i+1} (ID: {doc['id']}): {score:.3f}")

            # 添加分数到文档
            for i, doc in enumerate(documents):
                doc["rerank_score"] = float(scores[i])

            # 按重排序分数排序
            reranked = sorted(documents, key=lambda x: x.get("rerank_score", 0), reverse=True)

            # 打印重排序后的结果
            print("\n=== 重排序后结果 ===")
            for i, doc in enumerate(reranked[:top_k]):
                print(f"排名 {i+1} (ID: {doc['id']}): {doc['rerank_score']:.3f}")

            print("重排序完成")
            return reranked[:top_k]

        except Exception as e:
            print(f"重排序失败: {e}")
            return documents[:top_k]
    #执行检索和重排序
    def search(self, query: str, top_k: int = 5, use_rerank: bool = True) -> List[Dict]:
        """
        搜索相关文档

        Args:
            query: 查询语句
            top_k: 返回结果数量
            use_rerank: 是否使用重排序

        Returns:
            搜索结果列表
        """
        if not query or not query.strip():
            raise ValueError("查询语句不能为空")

        if not self.retriever:
            raise ValueError("检索器未初始化")

        print(f"搜索: '{query}'")

        try:
            # 执行检索
            retrieved_docs = self.retriever.invoke(query)

            if not retrieved_docs:
                print("未找到相关结果")
                return []

            print(f"检索到 {len(retrieved_docs)} 个结果")
            
            # 打印检索到的原始结果
            print("\n=== 检索器返回的原始结果 ===")
            for i, doc in enumerate(retrieved_docs):
                print(f"\n--- 结果 {i+1} ---")
                print(f"ID: {doc.metadata.get('id', 'N/A')}")
                print(f"类别: {doc.metadata.get('category', 'Unknown')}")
                print(f"行索引: {doc.metadata.get('row_index', 'N/A')}")
                print(f"内容预览: {doc.page_content[:200]}...")
                print("-" * 50)

            # 格式化结果
            formatted_results = []
            for i, doc in enumerate(retrieved_docs):
                result = {
                    "id": doc.metadata.get("id", i),
                    "category": doc.metadata.get("category", "Unknown"),
                    "content": doc.page_content,
                    "retrieval_score": 1.0 - (i * 0.1),  # 简单递减分数
                    "preview": doc.page_content[:150] + "..." if len(doc.page_content) > 150 else doc.page_content
                }
                formatted_results.append(result)

            # 打印格式化后的检索结果
            print("\n=== 格式化后的检索结果 ===")
            for i, result in enumerate(formatted_results):
                print(f"\n--- 格式化结果 {i+1} ---")
                print(f"ID: {result['id']}")
                print(f"类别: {result['category']}")
                print(f"检索分数: {result['retrieval_score']:.3f}")
                print(f"内容预览: {result['preview']}")
                print("-" * 50)

            # 可选的重新排序
            final_results = formatted_results[:top_k]
            if use_rerank and len(formatted_results) > 1:
                print("\n=== 开始重排序 ===")
                final_results = self._rerank_results(query, formatted_results, top_k)
            else:
                print("\n=== 跳过重排序，直接返回前 {top_k} 个结果 ===")
                final_results = formatted_results[:top_k]

            # 打印最终结果
            print("\n=== 最终返回结果 ===")
            for i, result in enumerate(final_results):
                print(f"\n--- 最终结果 {i+1} ---")
                print(f"ID: {result['id']}")
                print(f"类别: {result['category']}")
                if 'rerank_score' in result:
                    print(f"重排序分数: {result['rerank_score']:.3f}")
                else:
                    print(f"检索分数: {result['retrieval_score']:.3f}")
                print(f"内容预览: {result['preview']}")
                print("-" * 50)

            # 确保返回结果数量正确
            final_results = final_results[:top_k]

            print(f"返回 {len(final_results)} 个结果")
            return final_results

        except Exception as e:
            print(f"搜索失败: {e}")
            return []
    #让大模型对候选人进行评分
    def score_candidates(self, query: str, requirements: str, top_k: int = 5) -> str:
        """
        对候选人进行评分

        Args:
            query: 查询语句
            requirements: 岗位要求
            top_k: 候选人数量

        Returns:
            评分结果
        """
        # 检索候选人
        candidates = self.search(query, top_k=top_k, use_rerank=True)

        if not candidates:
            return "未找到符合条件的候选人"

        # 构建提示词
        prompt = f"""
你是一个专业的HR专家，请根据以下岗位要求对候选人进行评估。

## 岗位要求：
{requirements}

## 候选人信息：
"""

        for i, candidate in enumerate(candidates, 1):
            prompt += f"\n候选人{i} (ID: {candidate['id']}, 类别: {candidate['category']}):\n"
            prompt += f"匹配度: {candidate.get('rerank_score', candidate.get('retrieval_score', 0)):.3f}\n"
            prompt += f"简历信息:\n{candidate['content']}\n"
            prompt += "-" * 50 + "\n"

        prompt += """
## 评估要求：
请为每位候选人提供以下评估（使用中文）：
1. 技术能力匹配度 (0-10分)
2. 经验匹配度 (0-10分)
3. 综合评分 (0-10分)
4. 主要优势 (1-2点)
5. 主要不足 (1-2点)
6. 是否推荐 (是/否)

## 输出格式：
[候选人X]
- 技术能力: X/10
- 经验匹配: X/10
- 综合评分: X/10
- 优势: XXX
- 不足: XXX
- 推荐: 是/否

[最终推荐]
最佳候选人: [候选人编号]
理由: [简要说明]
"""

        # 调用LLM
        try:
            print("正在评估候选人...")
            response = self.llm.invoke(prompt)
            result = response.content if hasattr(response, 'content') else str(response)
            print("评估完成")
            return result

        except Exception as e:
            return f"评估失败: {e}"
    #简单的系统信息
    def get_system_info(self) -> Dict:
        """获取系统信息"""
        return {
            "documents_count": len(self.documents),
            "has_retriever": self.retriever is not None,
            "has_cross_encoder": self.cross_encoder is not None,
            "has_api_key": bool(self.api_key),
            "model": self.model_name
        }

#测试函数
def quick_test():
    """快速测试函数"""
    print("=" * 60)
    print("快速测试RAG系统")
    print("=" * 60)

    # 检查环境变量
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("Gemini_Api_Key")
    if not api_key:
        print("警告: 未设置API Key")
        print("请在 .env 文件中设置 OPENAI_API_KEY")
        print("或通过命令设置: export OPENAI_API_KEY='your-key-here'")
        print("\n将使用本地检索器（无LLM功能）")

    # 创建测试数据
    test_file = "test_resumes.csv"
    if not os.path.exists(test_file):
        print("\n创建测试数据...")
        test_data = {
            'Category': ['Data Scientist', 'Software Engineer', 'Web Developer', 'Data Scientist',
                         'Machine Learning Engineer'],
            'Resume': [
                'Experienced data scientist with 5 years in Python, machine learning, and statistical analysis. Strong background in NLP and deep learning.',
                'Senior software engineer with expertise in Java, Python, and cloud technologies. 8 years of experience in backend development.',
                'Full-stack web developer with 4 years of experience in JavaScript, React, Node.js, and modern web frameworks.',
                'Junior data scientist with 2 years experience in Python, pandas, and scikit-learn. Strong analytical skills and quick learner.',
                'Machine learning engineer with 6 years experience in TensorFlow, PyTorch, and MLOps. Published papers in top conferences.'
            ]
        }
        df = pd.DataFrame(test_data)
        df.to_csv(test_file, index=False)
        print(f"创建测试文件: {test_file}")

    try:
        # 初始化RAG
        print("\n初始化RAG系统...")
        rag = SimpleRAG(test_file)

        # 显示系统信息
        info = rag.get_system_info()
        print(f"\n系统信息:")
        for key, value in info.items():
            print(f"  {key}: {value}")

        # 测试搜索
        test_queries = [
            "有Python经验的候选人",
            "寻找数据科学家",
            "需要Web开发经验"
        ]

        for query in test_queries:
            print(f"\n{'=' * 50}")
            print(f"查询: {query}")
            print(f"{'=' * 50}")

            results = rag.search(query, top_k=2)

            if results:
                for i, result in enumerate(results, 1):
                    print(f"\n{i}. ID: {result['id']}, 类别: {result['category']}")
                    print(f"   分数: {result.get('rerank_score', result.get('retrieval_score', 0)):.4f}")
                    print(f"   预览: {result['preview']}")
            else:
                print("未找到结果")

        # 测试评估（如果有API Key）
        if api_key:
            print(f"\n{'=' * 50}")
            print("测试候选人评估")
            print(f"{'=' * 50}")

            query = "数据科学家"
            requirements = """
岗位: 高级数据科学家
要求:
1. 3年以上数据科学相关经验
2. 精通Python和机器学习库
3. 有深度学习项目经验
4. 良好的沟通能力
5. 有发表论文者优先
            """

            evaluation = rag.score_candidates(query, requirements, top_k=3)
            print("\n评估结果:")
            print(evaluation)
        else:
            print("\n跳过评估测试（需要API Key）")

        # 清理
        if os.path.exists(test_file) and test_file == "test_resumes.csv":
            os.remove(test_file)
            print(f"\n已清理测试文件: {test_file}")

    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()

#主函数
def main():
    """主函数 - 使用真实数据"""
    # 设置你的CSV文件路径
    csv_path = "/rag_project/rag_system/UpdatedResumeDataSet.csv"

    if not os.path.exists(csv_path):
        print(f"错误: 文件不存在 - {csv_path}")
        print("请确保CSV文件路径正确")
        return

    try:
        print("初始化RAG系统...")
        rag = SimpleRAG(csv_path)

        # 显示系统状态
        info = rag.get_system_info()
        print(f"\n系统状态:")
        for key, value in info.items():
            print(f"  {key}: {value}")

        # 交互式搜索
        while True:
            print(f"\n{'=' * 50}")
            query = input("请输入搜索查询 (输入 'quit' 退出): ").strip()

            if query.lower() in ['quit', 'exit', 'q']:
                print("再见！")
                break

            if not query:
                print("查询不能为空")
                continue

            # 搜索
            results = rag.search(query, top_k=5)

            if results:
                print(f"\n找到 {len(results)} 个结果:")
                for i, result in enumerate(results, 1):
                    print(f"\n{i}. ID: {result['id']}")
                    print(f"   类别: {result['category']}")
                    score = result.get('rerank_score', result.get('retrieval_score', 0))
                    print(f"   匹配度: {score:.4f}")
                    print(f"   预览: {result['preview'][:100]}...")
            else:
                print("未找到相关结果")

    except Exception as e:
        print(f"运行失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 首先运行快速测试
    quick_test()

    # 如果测试成功，可以取消下面的注释来运行完整版本
    # main()