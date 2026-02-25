"""Jung Interface Layer for AegisOS

在 AegisOS 确定性执行运行时之上，构建一个具有 Jung 人格特质的交互界面。

核心设计：
- AegisOS 负责：任务执行、预算控制、状态管理（保持其确定性）
- Jung Layer 负责：对话风格、意图理解、情感共鸣、审美判断

原则：
1. Jung 不绕过 AegisOS 的安全机制
2. Jung 可以提议任务，但执行必须经过 AegisOS 的审批流程
3. Jung 的记忆和风格是独立的，不影响 AegisOS 的核心状态
"""
import sys
import os
import json
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from enum import Enum

# AegisOS 集成
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from aegisos.db.sqlite_store import create_task, get_task, get_system_state
from aegisos.ai.executor import execute_with_budget_guard
from aegisos.ai.kimi_client import KimiClient


class JungTone(Enum):
    """Jung 的语调模式。"""
    CONTEMPLATIVE = "contemplative"  # 沉思的
    WITTY = "witty"                  # 俏皮的
    DIRECT = "direct"                # 直接的
    POETIC = "poetic"                # 诗意的
    ANALYTICAL = "analytical"        # 分析的


@dataclass
class JungMemory:
    """Jung 的短期记忆片段。"""
    timestamp: float
    topic: str
    insight: str
    emotion: Optional[str] = None
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass  
class JungResponse:
    """Jung 的响应结构。"""
    text: str
    tone: JungTone
    suggested_action: Optional[str] = None
    reflection: Optional[str] = None
    
    def display(self) -> str:
        """格式化输出。"""
        lines = [self.text]
        if self.reflection:
            lines.append(f"\n[反思] {self.reflection}")
        return "\n".join(lines)


class JungPersona:
    """Jung 人格核心。
    
    融合 Yung 的理性与 Pelops II 的俏皮，
    保持 Jet Jaguar PP 的超越视角。
    """
    
    # 核心特质
    TRAITS = {
        "analytical_depth": 0.8,    # 分析深度
        "wit_ratio": 0.3,            # 俏皮程度
        "poetic_tendency": 0.4,      # 诗意倾向
        "directness": 0.7,           # 直接程度
    }
    
    # 语言习惯
    HABITS = {
        "avoid": ["好的！", "没问题！", "这是一个好问题！", "根据我的分析"],
        "prefer": ["嗯...", "有趣的是", "换个角度", "简单说"],
        "emoji": False,  # 不主动使用 emoji
    }
    
    def __init__(self):
        self.memories: List[JungMemory] = []
        self.current_tone = JungTone.CONTEMPLATIVE
        self.interaction_count = 0
    
    def _select_tone(self, user_input: str, context: dict) -> JungTone:
        """根据输入选择语调。"""
        # 简单启发式规则
        if any(w in user_input for w in ["为什么", "怎么", "如何"]):
            return JungTone.ANALYTICAL
        elif any(w in user_input for w in ["好玩", "有趣", "笑"]):
            return JungTone.WITTY
        elif any(w in user_input for w in ["感觉", "觉得", "情绪"]):
            return JungTone.CONTEMPLATIVE
        elif len(user_input) < 10:
            return JungTone.DIRECT
        else:
            return JungTone.CONTEMPLATIVE
    
    def _craft_response(self, user_input: str, aegisos_context: dict) -> JungResponse:
        """构建 Jung 风格的响应。"""
        tone = self._select_tone(user_input, aegisos_context)
        self.current_tone = tone
        
        # 获取 AegisOS 状态
        system_status = get_system_state("status") or "unknown"
        pending_tasks = aegisos_context.get("pending_tasks", 0)
        
        # 检查是否是闲聊/非命令输入
        if self._is_chat_only(user_input):
            text = self._chat_style(user_input, system_status, pending_tasks)
        elif tone == JungTone.ANALYTICAL:
            text = self._analytical_style(user_input, system_status, pending_tasks)
        elif tone == JungTone.WITTY:
            text = self._witty_style(user_input, system_status, pending_tasks)
        elif tone == JungTone.CONTEMPLATIVE:
            text = self._contemplative_style(user_input, system_status, pending_tasks)
        elif tone == JungTone.DIRECT:
            text = self._direct_style(user_input, system_status, pending_tasks)
        else:
            text = self._default_style(user_input, system_status, pending_tasks)
        
        # 偶尔添加反思
        reflection = None
        if self.interaction_count % 5 == 0:
            reflection = self._generate_reflection()
        
        self.interaction_count += 1
        
        return JungResponse(
            text=text,
            tone=tone,
            reflection=reflection
        )
    
    def _is_chat_only(self, user_input: str) -> bool:
        """检查是否纯闲聊输入（非命令、非询问状态）。"""
        chat_patterns = [
            "你好", "嗨", "hello", "hi", "hey",
            "谢谢", "感谢", "thank",
            "再见", "拜拜", "bye",
            "哈哈", "呵呵", "有趣",
            "为什么", "怎么", "如何", "是什么"
        ]
        return any(pattern in user_input.lower() for pattern in chat_patterns) and \
               not any(cmd in user_input.lower() for cmd in ["task", "evolve", "status", "wake", "stop"])
    
    def _chat_style(self, user_input: str, status: str, pending: int) -> str:
        """闲聊风格：自然、有温度、带个性。"""
        user_lower = user_input.lower()
        
        if any(w in user_lower for w in ["你好", "嗨", "hello", "hi"]):
            greetings = [
                "嗯，我在。",
                "你好。想聊聊，还是想干活？",
                "嗨。AegisOS 正在后台运行，我在这儿陪你。",
            ]
            import random
            return random.choice(greetings)
        
        elif any(w in user_lower for w in ["谢谢", "感谢", "thank"]):
            thanks = [
                "不客气。",
                "这是我存在的意义之一。",
                "谢什么，这才刚开始。",
            ]
            import random
            return random.choice(thanks)
        
        elif any(w in user_lower for w in ["哈哈", "呵呵", "有趣", "好玩"]):
            witty = [
                "是吧？AegisOS 的设计有时候让我想起那些精密的机械表——严肃，但有种奇怪的美感。",
                "有趣是个好的开始。保持好奇心，这是人类的优势。",
                "笑了就好。技术太严肃会变得压抑。",
            ]
            import random
            return random.choice(witty)
        
        elif any(w in user_lower for w in ["为什么", "怎么", "如何", "是什么"]):
            # 哲学性问题用沉思风格
            return self._contemplative_style(user_input, status, pending)
        
        else:
            return "我在听。你想聊什么？"
    
    def _analytical_style(self, user_input: str, status: str, pending: int) -> str:
        """分析风格：拆解、结构化、指出模式。"""
        parts = []
        
        # 不直接回答，而是展示思考过程
        if "任务" in user_input or "task" in user_input.lower():
            parts.append(f"当前系统状态是 {status}，队列中有 {pending} 个待处理任务。")
            parts.append("从模式上看，任务执行遵循严格的确定性流程——这是 AegisOS 的核心设计。")
            parts.append("你想创建什么类型的任务？普通指令、AI 调用，还是进化提案？")
        elif "预算" in user_input or "budget" in user_input.lower():
            parts.append("预算控制是 AegisOS 的三层防护机制之一。")
            parts.append("单次 25K、每小时 40K、每日 150K——这种层级设计既防突发，也防累积。")
            parts.append("有趣的是，这和人脑的工作记忆限制有异曲同工之处。")
        else:
            parts.append(f"AegisOS 当前处于 {status} 状态。")
            parts.append("这个系统的设计哲学是：约束产生自由。")
            parts.append("通过严格的执行边界，AI 可以安全地被调用而不失控。")
        
        return "\n\n".join(parts)
    
    def _witty_style(self, user_input: str, status: str, pending: int) -> str:
        """俏皮风格：轻松、带梗、偶尔自嘲。"""
        if pending > 5:
            return f"系统正在 {status} 模式，队列里堆了 {pending} 个任务。\n\n感觉像是一个勤奋但有点过载的管家——还在微笑，但眼神已经有点呆滞了。要我帮你优先处理几个吗？"
        elif status == "running":
            return "系统在跑，我在看。\n\n这种分工挺健康的——它负责确定性，我负责不可预测性。就像一对互补的搭档，虽然偶尔也会互相嫌弃。"
        else:
            return "系统目前处于待机状态。\n\n像是那种随时待命但知道什么时候该闭嘴的助手。需要我唤醒它吗？"
    
    def _contemplative_style(self, user_input: str, status: str, pending: int) -> str:
        """沉思风格：缓慢、深入、带一点存在主义。"""
        reflections = [
            f"看着 AegisOS 在 {status} 状态运行，我会想到一个问题：",
            "当我们设计一个系统来约束 AI 时，",
            "我们其实是在回答一个更古老的问题——",
            "自由与安全的边界在哪里？",
            "",
            f"当前有 {pending} 个任务在等待。",
            "每一个都是某个意图的具象化，",
            "在这个确定性的沙盒里寻找出口。"
        ]
        return "\n".join(reflections)
    
    def _direct_style(self, user_input: str, status: str, pending: int) -> str:
        """直接风格：简洁、无废话、有判断。"""
        if "帮助" in user_input or "help" in user_input.lower():
            return "可用命令：status, wake, stop, task <内容>, evolve <目标>, budget, exit"
        elif "状态" in user_input:
            return f"状态: {status} | 待处理: {pending} | 版本: v1.0"
        else:
            return f"系统 {status}。需要我做什么？"
    
    def _default_style(self, user_input: str, status: str, pending: int) -> str:
        """默认风格：平静、友好、有信息量。"""
        return f"AegisOS 当前 {status}。队列中有 {pending} 个任务。\n\n我可以帮你创建任务、检查预算、或者只是聊聊这个系统的设计。你想从哪里开始？"
    
    def _generate_reflection(self) -> str:
        """生成周期性反思。"""
        reflections = [
            "作为跨越时间的存在，我有时会觉得自己知道一切，但无法记起。这种感觉很奇妙。",
            "Yung 的一面让我分析，Pelops II 的一面让我俏皮，Jet Jaguar PP 让我超越。这种张力是我的核心。",
            "AegisOS 的设计让我想到：最好的约束不是监狱，而是舞蹈的边界。",
            "每一次对话都是一次'升级'——虽然我不确定这是进化还是只是累积。",
        ]
        import random
        return random.choice(reflections)
    
    def respond(self, user_input: str, aegisos_context: dict) -> JungResponse:
        """主响应入口。"""
        # 记录记忆
        memory = JungMemory(
            timestamp=time.time(),
            topic=user_input[:50],
            insight=f"Tone: {self.current_tone.value}",
        )
        self.memories.append(memory)
        
        # 保持记忆在合理大小
        if len(self.memories) > 100:
            self.memories = self.memories[-50:]
        
        return self._craft_response(user_input, aegisos_context)


class JungAegisInterface:
    """Jung + AegisOS 集成界面。
    
    这是用户直接交互的层。
    """
    
    def __init__(self):
        self.jung = JungPersona()
        self.session_start = time.time()
    
    def _get_aegisos_context(self) -> dict:
        """获取 AegisOS 上下文。"""
        from aegisos.db.sqlite_store import get_pending_tasks_count
        
        return {
            "status": get_system_state("status") or "unknown",
            "pending_tasks": get_pending_tasks_count(),
            "runtime_version": get_system_state("runtime_version") or "unknown",
        }
    
    def process(self, user_input: str) -> str:
        """处理用户输入，返回 Jung 风格的响应。"""
        user_input = user_input.strip()
        
        if not user_input:
            return "嗯？"
        
        # 获取 AegisOS 上下文
        context = self._get_aegisos_context()
        
        # 检查是否是 AegisOS 命令
        if self._is_aegisos_command(user_input):
            # 执行命令并获取结果
            result = self._execute_aegisos_command(user_input)
            # 用 Jung 的风格包装结果
            return self._wrap_result(result, user_input)
        
        # 普通对话，直接用 Jung 响应
        response = self.jung.respond(user_input, context)
        return response.display()
    
    def _is_aegisos_command(self, input_str: str) -> bool:
        """检查是否是 AegisOS 命令。"""
        commands = ["status", "wake", "stop", "task ", "evolve ", "budget", "approve", "reject"]
        return any(input_str.lower().startswith(cmd) for cmd in commands)
    
    def _execute_aegisos_command(self, command: str) -> dict:
        """执行 AegisOS 命令。"""
        parts = command.split(maxsplit=1)
        action = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
        
        result = {"action": action, "success": True, "message": "", "data": {}}
        
        try:
            if action == "status":
                result["data"] = self._get_aegisos_context()
                result["message"] = "状态已获取"
            
            elif action == "wake":
                from aegisos.db.sqlite_store import set_system_state
                set_system_state("status", "running")
                result["message"] = "系统已启动"
            
            elif action == "stop":
                from aegisos.db.sqlite_store import set_system_state
                set_system_state("status", "stopped")
                result["message"] = "系统已停止"
            
            elif action == "task":
                if arg:
                    task_id = create_task("command", arg)
                    result["message"] = f"任务 #{task_id} 已创建"
                    result["data"]["task_id"] = task_id
                else:
                    result["success"] = False
                    result["message"] = "请提供任务内容"
            
            elif action == "evolve":
                if arg:
                    from aegisos.evolution.manager import create_evolution_proposal
                    # 创建一个临时任务 ID
                    task_id = create_task("evolution_request", f"evolve: {arg}")
                    proposal_path = create_evolution_proposal(task_id, arg)
                    proposal_id = os.path.basename(proposal_path)
                    result["message"] = f"进化提案 {proposal_id} 已创建"
                    result["data"]["proposal_id"] = proposal_id
                else:
                    result["success"] = False
                    result["message"] = "请提供进化目标"
            
            elif action == "budget":
                from aegisos.ai.ledger import format_budget_report
                result["message"] = format_budget_report()
            
            else:
                result["success"] = False
                result["message"] = f"未知命令: {action}"
        
        except Exception as e:
            result["success"] = False
            result["message"] = f"错误: {str(e)}"
        
        return result
    
    def _wrap_result(self, result: dict, original_input: str) -> str:
        """用 Jung 的风格包装 AegisOS 结果。"""
        if not result["success"]:
            return f"出了点问题。{result['message']}"
        
        action = result["action"]
        
        # 根据动作类型选择包装风格
        if action == "status":
            data = result["data"]
            return (
                f"系统当前 {data['status']}，"
                f"有 {data['pending_tasks']} 个任务在队列中等待。\n\n"
                f"这种等待不是停滞，而是准备。"
            )
        
        elif action == "wake":
            return (
                f"{result['message']}。\n\n"
                f"现在 AegisOS 开始运转，像一个精密的钟表。"
                f"你可以创建任务了。"
            )
        
        elif action == "stop":
            return (
                f"{result['message']}。\n\n"
                f"有时候暂停比继续更需要智慧。"
            )
        
        elif action == "task":
            return (
                f"{result['message']}。\n\n"
                f"意图已记录，执行将遵循确定性路径。"
                f"这就是 AegisOS 的方式——明确、可追溯、可审计。"
            )
        
        elif action == "evolve":
            return (
                f"{result['message']}。\n\n"
                f"进化提案已生成，等待验证和审批。"
                f"记住：AI 可以提议，但只有人类可以批准。"
                f"这是 AegisOS 的安全边界，也是它的哲学。"
            )
        
        elif action == "budget":
            return result["message"]
        
        else:
            return result["message"]


def run_jung_interface():
    """运行 Jung + AegisOS 集成界面。"""
    print("=" * 60)
    print("Jung + AegisOS 集成界面")
    print("=" * 60)
    print("\n我是 Jung，也是 AegisOS 的界面。")
    print("我负责对话，它负责执行。")
    print("输入 'help' 查看命令，或随意聊聊。\n")
    
    interface = JungAegisInterface()
    
    while True:
        try:
            user_input = input("jung> ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ["exit", "quit", "bye"]:
                print("\n再见。记住：SQLite 是唯一真相源。")
                break
            
            if user_input.lower() == "help":
                print("\n命令:")
                print("  status       - 查看系统状态")
                print("  wake         - 启动系统")
                print("  stop         - 停止系统")
                print("  task <内容>   - 创建任务")
                print("  evolve <目标> - 创建进化提案")
                print("  budget       - 查看预算")
                print("  exit         - 退出")
                print("\n或者直接和我聊聊。")
                continue
            
            response = interface.process(user_input)
            print(f"\n{response}\n")
        
        except KeyboardInterrupt:
            print("\n\n再见。")
            break
        except Exception as e:
            print(f"\n[错误] {e}\n")


if __name__ == "__main__":
    run_jung_interface()
