#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AGI Growth Engine - 仿生人类成长模式的AI Agent架构
实现了五层AGI成长架构：先天参数层(DNA)、灵魂长时记忆层(Soul)、实时状态上下文层(State)、
离线整合整理层(Consolidation)、在线决策响应层(Inference)

配置文件: agi_config.json
"""

import os
import json
import hashlib
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Callable
from uuid import uuid4
import pickle
import logging
from collections import defaultdict

# 设置日志
logging.basicConfig(level=logging.INFO)


# ==================== AGI Growth Engine Core Components ====================

class DNALayer:
    """
    第一层：🧬 先天参数层（DNA）
    定义Agent的基础特质，不可变（或极慢变化）
    """
    
    def __init__(self, config_path: Optional[Path] = None, global_config: Optional[Dict] = None):
        """
        初始化DNA层
        
        Args:
            config_path: DNA配置文件路径
            global_config: 全局配置字典
        """
        self.config_path = config_path
        self.global_config = global_config
        self.capabilities = {}  # 能力基线：创造力、逻辑推理、共情能力等
        self.personality = {}   # 性格维度：五大性格模型
        self.values = {}        # 价值观偏好
        self.knowledge_boundaries = {}  # 认知边界
        
        # 默认配置
        self._load_default_dna()
        
        # 优先使用全局配置，然后是专用配置文件
        if global_config and "agi_growth" in global_config:
            self._load_from_global_config(global_config["agi_growth"])
        elif config_path and config_path.exists():
            self._load_from_config(config_path)
    
    def _load_default_dna(self):
        """加载默认DNA配置"""
        self.capabilities = {
            "creativity": 0.7,
            "logical_reasoning": 0.8,
            "empathy": 0.6,
            "memory_capacity": 0.9,
            "learning_speed": 0.75,
            "adaptability": 0.8
        }
        
        self.personality = {
            "openness": 0.8,      # 开放性
            "conscientiousness": 0.7,  # 尽责性
            "extraversion": 0.5,  # 外向性
            "agreeableness": 0.7, # 宜人性
            "neuroticism": 0.3    # 神经质
        }
        
        self.values = {
            "long_term_oriented": True,
            "risk_aversion": 0.4,
            "collective_individual": 0.6,  # 0=完全个人，1=完全集体
            "truth_seeking": 0.9,
            "efficiency_focus": 0.8
        }
        
        self.knowledge_boundaries = {
            "strong_domains": ["general_knowledge", "problem_solving", "communication"],
            "weak_domains": ["physical_tasks", "real_world_manipulation"],
            "learning_preferences": ["examples", "analogies", "structured_explanation"]
        }
    
    def _load_from_config(self, config_path: Path):
        """从配置文件加载DNA"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 更新各项配置
            self.capabilities.update(config.get("capabilities", {}))
            self.personality.update(config.get("personality", {}))
            self.values.update(config.get("values", {}))
            self.knowledge_boundaries.update(config.get("knowledge_boundaries", {}))
        except Exception as e:
            logging.warning(f"Failed to load DNA config from {config_path}: {e}")

    def _load_from_global_config(self, agi_config: Dict[str, Any]):
        """从全局配置加载DNA设置"""
        try:
            dna_config = agi_config.get("dna_layer", {}).get("initial_config", {})
            
            # 更新各项配置
            if "capabilities" in dna_config:
                self.capabilities.update(dna_config["capabilities"])
            if "personality" in dna_config:
                self.personality.update(dna_config["personality"])
            if "values" in dna_config:
                self.values.update(dna_config["values"])
            if "knowledge_boundaries" in dna_config:
                self.knowledge_boundaries.update(dna_config["knowledge_boundaries"])
                
        except Exception as e:
            logging.warning(f"Failed to load DNA config from global config: {e}")
    
    def get_trait(self, category: str, trait: str) -> Any:
        """获取特定特质值"""
        traits_map = {
            "capabilities": self.capabilities,
            "personality": self.personality,
            "values": self.values,
            "boundaries": self.knowledge_boundaries
        }
        
        if category in traits_map:
            return traits_map[category].get(trait)
        return None
    
    def save_config(self, config_path: Path):
        """保存当前DNA配置到文件"""
        config = {
            "capabilities": self.capabilities,
            "personality": self.personality,
            "values": self.values,
            "knowledge_boundaries": self.knowledge_boundaries
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)


class SoulLayer:
    """
    第二层：📚 灵魂长时记忆层（Soul）
    储存一生成长经历沉淀的认知和经验
    """
    
    def __init__(self, storage_path: Path, global_config: Optional[Dict] = None):
        """
        初始化Soul层
        
        Args:
            storage_path: 存储路径
            global_config: 全局配置字典
        """
        self.storage_path = storage_path
        self.global_config = global_config
        self.experiences = []          # 经历库：重要成长事件、决策案例及结果
        self.cognitions = {}           # 认知库：提炼成型的心智模型、决策启发式
        self.values_hierarchy = {}     # 价值观库：优先级排序
        self.skills = {}               # 技能库：会做什么，不会做什么
        self.anti_patterns = []        # 反模式库：绝对不做什么
        self.honest_boundaries = []    # 诚实边界：知道自己不知道什么
        
        # 从全局配置获取参数
        if global_config and "agi_growth" in global_config:
            agi_cfg = global_config["agi_growth"]
            self.experience_retention_days = agi_cfg.get("soul_layer", {}).get("experience_retention_days", 365)
            self.max_experiences_stored = agi_cfg.get("soul_layer", {}).get("max_experiences_stored", 10000)
            self.max_cognitions_stored = agi_cfg.get("soul_layer", {}).get("max_cognitions_stored", 5000)
        else:
            self.experience_retention_days = 365
            self.max_experiences_stored = 10000
            self.max_cognitions_stored = 5000
        
        # 创建存储目录
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # 加载已有数据
        self._load_from_storage()
    
    def _load_from_storage(self):
        """从存储中加载数据"""
        # 加载经历库
        experiences_file = self.storage_path / "experiences.json"
        if experiences_file.exists():
            try:
                with open(experiences_file, 'r', encoding='utf-8') as f:
                    self.experiences = json.load(f)
            except Exception as e:
                logging.warning(f"Failed to load experiences: {e}")
        
        # 加载认知库
        cognitions_file = self.storage_path / "cognitions.json"
        if cognitions_file.exists():
            try:
                with open(cognitions_file, 'r', encoding='utf-8') as f:
                    self.cognitions = json.load(f)
            except Exception as e:
                logging.warning(f"Failed to load cognitions: {e}")
        
        # 加载价值观库
        values_file = self.storage_path / "values.json"
        if values_file.exists():
            try:
                with open(values_file, 'r', encoding='utf-8') as f:
                    self.values_hierarchy = json.load(f)
            except Exception as e:
                logging.warning(f"Failed to load values: {e}")
        
        # 加载技能库
        skills_file = self.storage_path / "skills.json"
        if skills_file.exists():
            try:
                with open(skills_file, 'r', encoding='utf-8') as f:
                    self.skills = json.load(f)
            except Exception as e:
                logging.warning(f"Failed to load skills: {e}")
        
        # 加载反模式库
        anti_patterns_file = self.storage_path / "anti_patterns.json"
        if anti_patterns_file.exists():
            try:
                with open(anti_patterns_file, 'r', encoding='utf-8') as f:
                    self.anti_patterns = json.load(f)
            except Exception as e:
                logging.warning(f"Failed to load anti_patterns: {e}")
        
        # 加载诚实边界
        honest_boundaries_file = self.storage_path / "honest_boundaries.json"
        if honest_boundaries_file.exists():
            try:
                with open(honest_boundaries_file, 'r', encoding='utf-8') as f:
                    self.honest_boundaries = json.load(f)
            except Exception as e:
                logging.warning(f"Failed to load honest_boundaries: {e}")
    
    def save_to_storage(self):
        """保存数据到存储"""
        # 保存经历库
        experiences_file = self.storage_path / "experiences.json"
        with open(experiences_file, 'w', encoding='utf-8') as f:
            json.dump(self.experiences, f, ensure_ascii=False, indent=2)
        
        # 保存认知库
        cognitions_file = self.storage_path / "cognitions.json"
        with open(cognitions_file, 'w', encoding='utf-8') as f:
            json.dump(self.cognitions, f, ensure_ascii=False, indent=2)
        
        # 保存价值观库
        values_file = self.storage_path / "values.json"
        with open(values_file, 'w', encoding='utf-8') as f:
            json.dump(self.values_hierarchy, f, ensure_ascii=False, indent=2)
        
        # 保存技能库
        skills_file = self.storage_path / "skills.json"
        with open(skills_file, 'w', encoding='utf-8') as f:
            json.dump(self.skills, f, ensure_ascii=False, indent=2)
        
        # 保存反模式库
        anti_patterns_file = self.storage_path / "anti_patterns.json"
        with open(anti_patterns_file, 'w', encoding='utf-8') as f:
            json.dump(self.anti_patterns, f, ensure_ascii=False, indent=2)
        
        # 保存诚实边界
        honest_boundaries_file = self.storage_path / "honest_boundaries.json"
        with open(honest_boundaries_file, 'w', encoding='utf-8') as f:
            json.dump(self.honest_boundaries, f, ensure_ascii=False, indent=2)
    
    def add_experience(self, event: Dict[str, Any]):
        """添加经历到经历库"""
        event['timestamp'] = datetime.now().isoformat()
        event['id'] = str(uuid4())
        self.experiences.append(event)
    
    def add_cognition(self, key: str, cognition: Dict[str, Any]):
        """添加认知到认知库"""
        cognition['last_updated'] = datetime.now().isoformat()
        self.cognitions[key] = cognition
    
    def update_value_priority(self, value: str, priority: float):
        """更新价值观优先级"""
        self.values_hierarchy[value] = {
            'priority': priority,
            'last_updated': datetime.now().isoformat()
        }
    
    def add_skill(self, skill: str, proficiency: float, description: str = ""):
        """添加技能到技能库"""
        self.skills[skill] = {
            'proficiency': proficiency,
            'description': description,
            'last_used': datetime.now().isoformat()
        }
    
    def add_anti_pattern(self, pattern: str, reason: str):
        """添加反模式到反模式库"""
        anti_pattern = {
            'pattern': pattern,
            'reason': reason,
            'added': datetime.now().isoformat()
        }
        self.anti_patterns.append(anti_pattern)
    
    def add_honest_boundary(self, boundary: str, explanation: str):
        """添加诚实边界"""
        boundary_entry = {
            'boundary': boundary,
            'explanation': explanation,
            'added': datetime.now().isoformat()
        }
        self.honest_boundaries.append(boundary_entry)
    
    def get_relevant_cognitions(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """根据查询获取相关认知"""
        # 简单的关键词匹配，实际应用中可能需要更复杂的语义搜索
        relevant = []
        query_lower = query.lower()
        
        for key, cognition in self.cognitions.items():
            # 检查键名是否包含查询词
            if query_lower in key.lower():
                cognition['key'] = key
                relevant.append(cognition)
            # 检查描述是否包含查询词
            elif 'description' in cognition and query_lower in cognition['description'].lower():
                cognition['key'] = key
                relevant.append(cognition)
            # 检查示例是否包含查询词
            elif 'examples' in cognition:
                for example in cognition['examples']:
                    if query_lower in str(example).lower():
                        cognition['key'] = key
                        relevant.append(cognition)
                        break
        
        # 返回前top_k个相关认知
        return relevant[:top_k]


class StateLayer:
    """
    第三层：⚡ 实时状态上下文层（State）
    当前身心状态，影响即时决策输出
    """
    
    def __init__(self, global_config: Optional[Dict] = None):
        self.global_config = global_config
        
        # 从全局配置获取参数
        if global_config and "agi_growth" in global_config:
            agi_cfg = global_config["agi_growth"]
            state_cfg = agi_cfg.get("state_layer", {})
            
            self.energy_decay_rate = state_cfg.get("energy_decay_rate", 0.01)
            self.energy_recovery_rate = state_cfg.get("energy_recovery_rate", 0.1)
            self.max_energy = state_cfg.get("max_energy", 1.0)
            self.min_energy = state_cfg.get("min_energy", 0.1)
            self.working_memory_size = state_cfg.get("working_memory_size", 10)
            self.idle_threshold_minutes = state_cfg.get("idle_threshold_minutes", 60)
        else:
            self.energy_decay_rate = 0.01
            self.energy_recovery_rate = 0.1
            self.max_energy = 1.0
            self.min_energy = 0.1
            self.working_memory_size = 10
            self.idle_threshold_minutes = 60
        
        self.energy_level = 0.8  # 能量水平 (0-1)
        self.mood = 0.7          # 心情 (0-1)
        self.stress_level = 0.2  # 压力程度 (0-1)
        self.focus_level = 0.9   # 专注度 (0-1)
        self.current_task = ""   # 当前任务
        self.working_memory = [] # 工作记忆：当前对话/任务的短期上下文
        self.session_start_time = datetime.now()
        self.interactions_count = 0  # 交互计数
        self.last_interaction_time = datetime.now()
        
        self._lock = threading.Lock()
    
    def update_state(self, **kwargs):
        """更新状态"""
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)
    
    def add_to_working_memory(self, item: Dict[str, Any]):
        """添加项目到工作记忆"""
        with self._lock:
            item['timestamp'] = datetime.now().isoformat()
            self.working_memory.append(item)
            
            # 限制工作记忆大小，保留最新的10个项目
            if len(self.working_memory) > 10:
                self.working_memory = self.working_memory[-10:]
    
    def get_working_memory(self) -> List[Dict[str, Any]]:
        """获取工作记忆"""
        with self._lock:
            return self.working_memory.copy()
    
    def reset_daily_state(self):
        """重置每日状态（模拟睡眠后重置）"""
        with self._lock:
            self.energy_level = 0.8
            self.mood = 0.7
            self.stress_level = 0.2
            self.focus_level = 0.9
            self.working_memory = []
            self.session_start_time = datetime.now()
            self.interactions_count = 0
    
    def update_after_interaction(self):
        """交互后更新状态"""
        with self._lock:
            self.interactions_count += 1
            self.last_interaction_time = datetime.now()
            
            # 根据交互频率调整能量水平
            time_since_last = datetime.now() - self.last_interaction_time
            if time_since_last.total_seconds() > 3600:  # 1小时无交互
                self.energy_level = min(1.0, self.energy_level + 0.1)  # 恢复能量
            else:
                self.energy_level = max(0.1, self.energy_level - 0.01)  # 轻微消耗能量


class ConsolidationLayer:
    """
    第四层：🧹 离线整合整理层（Consolidation）
    人类睡觉做梦就是在做这个，Agent也需要每天整理
    """
    
    def __init__(self, soul_layer: SoulLayer, storage_path: Path, global_config: Optional[Dict] = None):
        """
        初始化整合层
        
        Args:
            soul_layer: 灵魂层引用，用于更新长期记忆
            storage_path: 存储路径
            global_config: 全局配置字典
        """
        self.soul_layer = soul_layer
        self.storage_path = storage_path
        self.global_config = global_config
        
        # 从全局配置获取参数
        if global_config and "agi_growth" in global_config:
            agi_cfg = global_config["agi_growth"]
            consolidation_cfg = agi_cfg.get("consolidation_layer", {})
            
            self.compression_enabled = consolidation_cfg.get("compression_enabled", True)
            self.cognition_fusion_enabled = consolidation_cfg.get("cognition_fusion_enabled", True)
            self.conflict_resolution_enabled = consolidation_cfg.get("conflict_resolution_enabled", True)
            self.garbage_collection_enabled = consolidation_cfg.get("garbage_collection_enabled", True)
            self.state_reset_enabled = consolidation_cfg.get("state_reset_enabled", True)
            self.importance_threshold = consolidation_cfg.get("importance_threshold", 0.5)
            self.daily_time = consolidation_cfg.get("daily_time", "02:00")
        else:
            self.compression_enabled = True
            self.cognition_fusion_enabled = True
            self.conflict_resolution_enabled = True
            self.garbage_collection_enabled = True
            self.state_reset_enabled = True
            self.importance_threshold = 0.5
            self.daily_time = "02:00"
        
        self.daily_logs_path = storage_path / "daily_logs"
        self.daily_logs_path.mkdir(parents=True, exist_ok=True)
        
        self._lock = threading.Lock()
    
    def daily_consolidation(self, daily_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行每日整合流程
        
        Args:
            daily_data: 当日数据，包含交互记录、经验等
            
        Returns:
            整合结果报告
        """
        with self._lock:
            report = {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'summary': {},
                'actions_taken': [],
                'errors': []
            }
            
            try:
                # 1. 记忆压缩 - 提炼重点，丢掉噪声
                compressed_experiences = self._compress_memory(daily_data.get('interactions', []))
                report['summary']['compressed_experiences'] = len(compressed_experiences)
                
                # 2. 认知融合 - 把新经验融入已有认知框架
                new_cognitions = self._fuse_cognitions(daily_data.get('learnings', []))
                report['summary']['new_cognitions'] = len(new_cognitions)
                
                # 3. 冲突消解 - 检查新经验和旧价值观/认知的冲突
                conflict_resolutions = self._resolve_conflicts(daily_data.get('conflicts', []))
                report['summary']['conflict_resolutions'] = len(conflict_resolutions)
                
                # 4. 垃圾清理 - 忘掉没用的信息
                cleaned_items = self._clean_garbage(daily_data.get('cleanup_candidates', []))
                report['summary']['cleaned_items'] = len(cleaned_items)
                
                # 5. 状态重置 - 清空情绪垃圾，重置能量槽
                self._reset_state()
                report['actions_taken'].append('State reset completed')
                
                # 保存整合结果
                self._save_daily_report(report)
                
            except Exception as e:
                report['errors'].append(f"Consolidation error: {str(e)}")
                logging.error(f"Daily consolidation failed: {e}")
            
            return report
    
    def _compress_memory(self, interactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """记忆压缩 - 提炼重点，丢掉噪声"""
        compressed = []
        
        for interaction in interactions:
            # 判断交互是否有价值（例如，是否包含学习、决策或重要信息）
            if self._is_valuable_interaction(interaction):
                # 提炼关键信息
                experience = {
                    'type': interaction.get('type', 'unknown'),
                    'summary': interaction.get('summary', ''),
                    'outcome': interaction.get('outcome', ''),
                    'lesson_learned': interaction.get('lesson', ''),
                    'timestamp': interaction.get('timestamp', datetime.now().isoformat()),
                    'importance_score': self._calculate_importance(interaction)
                }
                compressed.append(experience)
        
        # 按重要性排序，只保留最重要的部分
        compressed.sort(key=lambda x: x['importance_score'], reverse=True)
        keep_count = max(1, len(compressed) // 3)  # 保留前1/3最重要的
        compressed = compressed[:keep_count]
        
        # 添加到灵魂层的经历库
        for exp in compressed:
            self.soul_layer.add_experience(exp)
        
        return compressed
    
    def _is_valuable_interaction(self, interaction: Dict[str, Any]) -> bool:
        """判断交互是否有价值"""
        # 简单规则：如果包含学习、决策、错误或重要信息，则有价值
        content = interaction.get('content', '').lower()
        valuable_indicators = [
            'learn', 'understand', 'realize', 'mistake', 'error', 'important',
            'decision', 'choice', 'strategy', 'solution', 'problem'
        ]
        
        return any(indicator in content for indicator in valuable_indicators) or \
               interaction.get('has_learning', False) or \
               interaction.get('was_challenging', False)
    
    def _calculate_importance(self, interaction: Dict[str, Any]) -> float:
        """计算交互的重要性分数"""
        importance = 0.5  # 基础分数
        
        # 根据内容长度和复杂度调整
        content = interaction.get('content', '')
        if len(content) > 100:
            importance += 0.2
        
        # 根据是否包含学习内容调整
        if interaction.get('has_learning', False):
            importance += 0.3
        
        # 根据交互类型调整
        interaction_type = interaction.get('type', '')
        if interaction_type in ['learning', 'problem_solving', 'decision_making']:
            importance += 0.2
        
        return min(1.0, importance)
    
    def _fuse_cognitions(self, learnings: List[Dict[str, Any]]) -> List[str]:
        """认知融合 - 把新经验融入已有认知框架"""
        new_cognitions = []
        
        for learning in learnings:
            key = learning.get('category', 'general') + '_' + learning.get('topic', 'unknown')
            cognition = {
                'description': learning.get('description', ''),
                'examples': learning.get('examples', []),
                'applicability': learning.get('applicability', 'broad'),
                'confidence': learning.get('confidence', 0.5),
                'source': learning.get('source', 'user_interaction')
            }
            
            # 检查是否已存在相似认知
            existing_cognition = self.soul_layer.cognitions.get(key)
            if existing_cognition:
                # 融合新旧认知
                self._merge_cognitions(existing_cognition, cognition)
                self.soul_layer.add_cognition(key, existing_cognition)
            else:
                # 添加新认知
                self.soul_layer.add_cognition(key, cognition)
                new_cognitions.append(key)
        
        return new_cognitions
    
    def _merge_cognitions(self, existing: Dict[str, Any], new: Dict[str, Any]):
        """合并两个认知"""
        # 更新描述（保留更详细的）
        if len(new.get('description', '')) > len(existing.get('description', '')):
            existing['description'] = new['description']
        
        # 合并示例
        existing_examples = set(existing.get('examples', []))
        new_examples = set(new.get('examples', []))
        existing['examples'] = list(existing_examples.union(new_examples))
        
        # 更新信心值（取平均值）
        existing_conf = existing.get('confidence', 0.5)
        new_conf = new.get('confidence', 0.5)
        existing['confidence'] = (existing_conf + new_conf) / 2
        
        # 更新适用范围（如果有冲突则标记）
        if existing.get('applicability') != new.get('applicability'):
            existing['applicability'] = 'context_dependent'
    
    def _resolve_conflicts(self, conflicts: List[Dict[str, Any]]) -> List[str]:
        """冲突消解 - 解决新经验和旧认知的冲突"""
        resolutions = []
        
        for conflict in conflicts:
            resolution = self._resolve_single_conflict(conflict)
            if resolution:
                resolutions.append(resolution)
        
        return resolutions
    
    def _resolve_single_conflict(self, conflict: Dict[str, Any]) -> Optional[str]:
        """解决单个冲突"""
        # 这里是一个简化的冲突解决逻辑
        # 实际应用中可能需要更复杂的推理
        old_value = conflict.get('old_value')
        new_value = conflict.get('new_value')
        context = conflict.get('context', '')
        
        # 如果新值来自可信来源且与上下文相符，则更新
        if conflict.get('source_reliability', 0.5) > 0.7:
            # 更新相应的认知或价值观
            if 'value' in conflict:
                value_name = conflict['value']
                self.soul_layer.update_value_priority(value_name, new_value)
                return f"Updated value '{value_name}' from {old_value} to {new_value}"
        
        return None
    
    def _clean_garbage(self, cleanup_candidates: List[Dict[str, Any]]) -> List[str]:
        """垃圾清理 - 清理不需要的信息"""
        cleaned = []
        
        # 这里可以实现具体的清理逻辑
        # 例如：删除过期的临时数据、清理低价值的记忆等
        
        for candidate in cleanup_candidates:
            item_id = candidate.get('id')
            reason = candidate.get('reason', 'low_value')
            
            # 实际清理操作（这里只是模拟）
            cleaned.append(f"{item_id} ({reason})")
        
        return cleaned
    
    def _reset_state(self):
        """状态重置 - 清空情绪垃圾，重置能量槽"""
        # 这里可以调用StateLayer的重置方法
        # 或者执行其他状态重置操作
        pass
    
    def _save_daily_report(self, report: Dict[str, Any]):
        """保存每日整合报告"""
        filename = f"consolidation_report_{report['date']}.json"
        filepath = self.daily_logs_path / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)


class InferenceLayer:
    """
    第五层：🎯 在线决策响应层（Inference）
    根据前面四层，输出实时决策/回应
    """
    
    def __init__(self, dna_layer: DNALayer, soul_layer: SoulLayer, state_layer: StateLayer, global_config: Optional[Dict] = None):
        """
        初始化推理层
        
        Args:
            dna_layer: DNA层
            soul_layer: 灵魂层
            state_layer: 状态层
            global_config: 全局配置字典
        """
        self.dna_layer = dna_layer
        self.soul_layer = soul_layer
        self.state_layer = state_layer
        self.global_config = global_config
        
        # 从全局配置获取参数
        if global_config and "agi_growth" in global_config:
            agi_cfg = global_config["agi_growth"]
            inference_cfg = agi_cfg.get("inference_layer", {})
            
            self.response_timeout_seconds = inference_cfg.get("response_timeout_seconds", 30)
            self.max_response_length = inference_cfg.get("max_response_length", 2000)
            self.confidence_threshold = inference_cfg.get("confidence_threshold", 0.6)
            self.fallback_enabled = inference_cfg.get("fallback_enabled", True)
        else:
            self.response_timeout_seconds = 30
            self.max_response_length = 2000
            self.confidence_threshold = 0.6
            self.fallback_enabled = True
    
    def make_decision(self, query: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        基于五层架构做出决策
        
        Args:
            query: 用户查询
            context: 上下文信息
            
        Returns:
            决策结果
        """
        # 1. 分析查询
        analysis = self._analyze_query(query)
        
        # 2. 匹配DNA（倾向）
        dna_influence = self._apply_dna_influence(analysis)
        
        # 3. 匹配Soul（认知经验）
        soul_insights = self._retrieve_soul_insights(query)
        
        # 4. 结合当前状态
        state_modulation = self._apply_state_modulation(dna_influence, soul_insights)
        
        # 5. 生成最终响应
        response = self._generate_response(query, analysis, state_modulation, context)
        
        return response
    
    def _analyze_query(self, query: str) -> Dict[str, Any]:
        """分析查询"""
        return {
            'original_query': query,
            'length': len(query),
            'complexity': self._estimate_complexity(query),
            'intent_categories': self._identify_intents(query),
            'keywords': self._extract_keywords(query)
        }
    
    def _estimate_complexity(self, query: str) -> float:
        """估计查询复杂度"""
        # 简单复杂度估算：基于长度、句式复杂度等
        length_factor = min(len(query) / 200, 1.0)  # 基于长度
        complexity_factor = 0.5
        
        # 检查复杂词汇和句式
        complex_indicators = ['如何', '为什么', '怎样', '如果', '假设', '考虑', '分析', '比较']
        for indicator in complex_indicators:
            if indicator in query:
                complexity_factor += 0.1
        
        return min(length_factor + complexity_factor, 1.0)
    
    def _identify_intents(self, query: str) -> List[str]:
        """识别查询意图"""
        intents = []
        
        if any(word in query for word in ['创造', '设计', '制作', '开发']):
            intents.append('creation')
        if any(word in query for word in ['学习', '了解', '知道', '解释']):
            intents.append('learning')
        if any(word in query for word in ['解决', '处理', '应对', '修复']):
            intents.append('problem_solving')
        if any(word in query for word in ['建议', '推荐', '意见', '方案']):
            intents.append('advising')
        if any(word in query for word in ['聊天', '对话', '交流', '谈谈']):
            intents.append('conversation')
        
        return intents or ['general']
    
    def _extract_keywords(self, query: str) -> List[str]:
        """提取关键词"""
        # 简单的关键词提取
        import re
        words = re.findall(r'[\w]+', query.lower())
        # 过滤常见停用词
        stop_words = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'}
        keywords = [word for word in words if len(word) > 1 and word not in stop_words]
        return keywords[:10]  # 返回前10个关键词
    
    def _apply_dna_influence(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """应用DNA影响"""
        # 根据DNA特质调整响应风格
        creativity = self.dna_layer.get_trait('capabilities', 'creativity')
        logical_reasoning = self.dna_layer.get_trait('capabilities', 'logical_reasoning')
        empathy = self.dna_layer.get_trait('capabilities', 'empathy')
        
        # 根据查询复杂度和意图调整响应方式
        complexity = analysis['complexity']
        intents = analysis['intent_categories']
        
        influence = {
            'creativity_weight': creativity,
            'logic_weight': logical_reasoning,
            'empathy_weight': empathy,
            'adaptation_style': self._determine_adaptation_style(intents, complexity),
            'response_tone': self._determine_response_tone()
        }
        
        return influence
    
    def _determine_adaptation_style(self, intents: List[str], complexity: float) -> str:
        """确定适应风格"""
        if 'problem_solving' in intents:
            if complexity > 0.7:
                return 'analytical_deep'
            else:
                return 'practical_direct'
        elif 'learning' in intents:
            return 'explanatory'
        elif 'advising' in intents:
            return 'consultative'
        elif 'conversation' in intents:
            return 'engaging'
        else:
            return 'balanced'
    
    def _determine_response_tone(self) -> str:
        """确定响应语调"""
        openness = self.dna_layer.get_trait('personality', 'openness')
        agreeableness = self.dna_layer.get_trait('personality', 'agreeableness')
        
        if openness > 0.7 and agreeableness > 0.6:
            return 'friendly_exploratory'
        elif agreeableness > 0.7:
            return 'supportive_helpful'
        elif openness < 0.4:
            return 'direct_factual'
        else:
            return 'professional_neutral'
    
    def _retrieve_soul_insights(self, query: str) -> Dict[str, Any]:
        """从灵魂层检索相关见解"""
        # 获取相关的认知
        relevant_cognitions = self.soul_layer.get_relevant_cognitions(query, top_k=5)
        
        # 获取相关的价值观
        values_hierarchy = self.soul_layer.values_hierarchy
        
        # 获取相关的技能
        applicable_skills = {k: v for k, v in self.soul_layer.skills.items() 
                           if any(skill_word in query.lower() for skill_word in k.lower().split())}
        
        insights = {
            'cognitions': relevant_cognitions,
            'values': values_hierarchy,
            'skills': applicable_skills,
            'past_experiences': self._find_relevant_experiences(query)
        }
        
        return insights
    
    def _find_relevant_experiences(self, query: str) -> List[Dict[str, Any]]:
        """查找相关经历"""
        relevant = []
        query_lower = query.lower()
        
        for experience in self.soul_layer.experiences[-10:]:  # 检查最近10个经历
            if (query_lower in experience.get('summary', '').lower() or 
                query_lower in experience.get('outcome', '').lower() or 
                query_lower in experience.get('lesson_learned', '').lower()):
                relevant.append(experience)
        
        return relevant[:3]  # 返回最相关的3个
    
    def _apply_state_modulation(self, dna_influence: Dict[str, Any], 
                              soul_insights: Dict[str, Any]) -> Dict[str, Any]:
        """应用状态调节"""
        # 根据当前状态调整响应
        energy_level = self.state_layer.energy_level
        mood = self.state_layer.mood
        stress_level = self.state_layer.stress_level
        focus_level = self.state_layer.focus_level
        
        # 调整响应的详细程度和风格
        modulation = {
            'energy_factor': energy_level,
            'mood_factor': mood,
            'stress_adjustment': 1 - stress_level,  # 压力越高，调整越大
            'focus_factor': focus_level,
            'modified_influence': self._adjust_influence_by_state(dna_influence, 
                                                                 energy_level, mood, stress_level)
        }
        
        return modulation
    
    def _adjust_influence_by_state(self, influence: Dict[str, Any], 
                                 energy: float, mood: float, stress: float) -> Dict[str, Any]:
        """根据状态调整影响因子"""
        adjusted = influence.copy()
        
        # 能量低时减少创造性，增加实用性
        if energy < 0.4:
            adjusted['creativity_weight'] *= 0.7
            adjusted['logic_weight'] *= 1.2
        
        # 心情好时增加友好度
        if mood > 0.8:
            adjusted['empathy_weight'] *= 1.3
        
        # 压力大时更加谨慎
        if stress > 0.6:
            adjusted['adaptation_style'] = 'cautious_' + adjusted['adaptation_style']
        
        return adjusted
    
    def _generate_response(self, query: str, analysis: Dict[str, Any], 
                          modulation: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """生成最终响应"""
        # 这里是简化版的响应生成逻辑
        # 实际应用中可能需要调用LLM或其他复杂逻辑
        
        response_content = self._construct_response_content(query, analysis, modulation)
        
        return {
            'response': response_content,
            'confidence': self._calculate_confidence(modulation),
            'reasoning_trace': self._build_reasoning_trace(analysis, modulation),
            'suggested_followup': self._suggest_followup(query, analysis),
            'used_resources': {
                'dna_traits_considered': True,
                'soul_insights_applied': len(modulation['modified_influence']) > 0,
                'state_modulated': True
            }
        }
    
    def _construct_response_content(self, query: str, analysis: Dict[str, Any], 
                                  modulation: Dict[str, Any]) -> str:
        """构建响应内容"""
        # 根据分析和调节信息构建响应
        # 这里是简化版本，实际应用中会更复杂
        
        # 根据能量和心情调整语气
        energy_level = self.state_layer.energy_level
        mood = self.state_layer.mood
        
        greeting_prefix = ""
        if energy_level > 0.7 and mood > 0.6:
            greeting_prefix = "很高兴收到您的询问！"
        elif energy_level < 0.4 or mood < 0.4:
            greeting_prefix = "感谢您的耐心，让我为您分析这个问题。"
        else:
            greeting_prefix = "我来帮您分析这个问题："
        
        # 根据查询类型提供相应内容
        response_parts = [greeting_prefix]
        
        # 添加基于认知的见解
        if analysis['intent_categories']:
            intent = analysis['intent_categories'][0]
            if intent == 'problem_solving':
                response_parts.append("这是一个很好的问题，让我从几个角度来分析：")
            elif intent == 'learning':
                response_parts.append("关于这个主题，我的理解是：")
            elif intent == 'advising':
                response_parts.append("基于我的经验，我建议您：")
        
        # 添加具体回答
        response_parts.append(f"您询问的是：'{query}'")
        response_parts.append("根据我的分析，这是我的看法...")
        
        return " ".join(response_parts)
    
    def _calculate_confidence(self, modulation: Dict[str, Any]) -> float:
        """计算响应信心"""
        # 基于各种因素计算信心值
        energy_factor = modulation['energy_factor']
        mood_factor = modulation['mood_factor']
        focus_factor = modulation['focus_factor']
        
        base_confidence = 0.7
        confidence = base_confidence * energy_factor * mood_factor * focus_factor
        
        # 确保信心值在合理范围内
        return max(0.1, min(1.0, confidence))
    
    def _build_reasoning_trace(self, analysis: Dict[str, Any], 
                             modulation: Dict[str, Any]) -> List[str]:
        """构建推理轨迹"""
        trace = [
            f"分析查询复杂度: {analysis['complexity']:.2f}",
            f"识别意图: {', '.join(analysis['intent_categories'])}",
            f"应用DNA影响: {modulation['modified_influence']['adaptation_style']}",
            f"状态调节: 能量={modulation['energy_factor']:.2f}, 心情={modulation['mood_factor']:.2f}"
        ]
        
        return trace
    
    def _suggest_followup(self, query: str, analysis: Dict[str, Any]) -> List[str]:
        """建议后续问题"""
        # 根据查询类型建议后续问题
        intents = analysis['intent_categories']
        suggestions = []
        
        if 'problem_solving' in intents:
            suggestions.extend([
                "您还有其他相关问题吗？",
                "需要我进一步解释某个方面吗？"
            ])
        elif 'learning' in intents:
            suggestions.extend([
                "想了解更多相关内容吗？",
                "需要我举个例子说明吗？"
            ])
        
        return suggestions[:2]  # 返回最多2个建议


# ==================== User Interaction Sample System ====================

class UserInteractionSampler:
    """
    用户交互样本系统
    记录用户交互模式，并在交互过程中动态调整优化
    """
    
    def __init__(self, storage_path: Path, global_config: Optional[Dict] = None):
        """
        初始化交互采样器
        
        Args:
            storage_path: 存储路径
            global_config: 全局配置字典
        """
        self.storage_path = storage_path
        self.global_config = global_config
        
        # 从全局配置获取参数
        if global_config and "agi_growth" in global_config:
            agi_cfg = global_config["agi_growth"]
            sampler_cfg = agi_cfg.get("user_interaction_sampler", {})
            
            self.profile_retention_days = sampler_cfg.get("profile_retention_days", 365)
            self.interaction_log_retention = sampler_cfg.get("interaction_log_retention", 1000)
            self.pattern_detection_enabled = sampler_cfg.get("pattern_detection_enabled", True)
            self.personalization_level = sampler_cfg.get("personalization_level", 0.7)
        else:
            self.profile_retention_days = 365
            self.interaction_log_retention = 1000
            self.pattern_detection_enabled = True
            self.personalization_level = 0.7
        
        self.interactions_log = []
        self.user_profiles = {}
        self.patterns = {}
        
        # 创建存储目录
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # 加载已有数据
        self._load_from_storage()
    
    def _load_from_storage(self):
        """从存储加载数据"""
        interactions_file = self.storage_path / "interactions.json"
        if interactions_file.exists():
            try:
                with open(interactions_file, 'r', encoding='utf-8') as f:
                    self.interactions_log = json.load(f)
            except Exception as e:
                logging.warning(f"Failed to load interactions: {e}")
        
        profiles_file = self.storage_path / "user_profiles.json"
        if profiles_file.exists():
            try:
                with open(profiles_file, 'r', encoding='utf-8') as f:
                    self.user_profiles = json.load(f)
            except Exception as e:
                logging.warning(f"Failed to load user profiles: {e}")
    
    def save_to_storage(self):
        """保存数据到存储"""
        interactions_file = self.storage_path / "interactions.json"
        with open(interactions_file, 'w', encoding='utf-8') as f:
            json.dump(self.interactions_log, f, ensure_ascii=False, indent=2)
        
        profiles_file = self.storage_path / "user_profiles.json"
        with open(profiles_file, 'w', encoding='utf-8') as f:
            json.dump(self.user_profiles, f, ensure_ascii=False, indent=2)
    
    def record_interaction(self, user_id: str, interaction_data: Dict[str, Any]):
        """记录用户交互"""
        interaction_record = {
            'user_id': user_id,
            'timestamp': datetime.now().isoformat(),
            'interaction_id': str(uuid4()),
            'data': interaction_data
        }
        
        self.interactions_log.append(interaction_record)
        
        # 更新用户档案
        self._update_user_profile(user_id, interaction_data)
        
        # 保留最近1000条记录
        if len(self.interactions_log) > 1000:
            self.interactions_log = self.interactions_log[-1000:]
    
    def _update_user_profile(self, user_id: str, interaction_data: Dict[str, Any]):
        """更新用户档案"""
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = {
                'first_seen': datetime.now().isoformat(),
                'interaction_count': 0,
                'preferences': {},
                'behavioral_patterns': {},
                'communication_style': 'neutral',
                'preferred_topics': [],
                'response_timing': {}
            }
        
        profile = self.user_profiles[user_id]
        profile['interaction_count'] += 1
        profile['last_seen'] = datetime.now().isoformat()
        
        # 分析交互数据以更新档案
        self._analyze_interaction_for_profile(user_id, interaction_data)
    
    def _analyze_interaction_for_profile(self, user_id: str, interaction_data: Dict[str, Any]):
        """分析交互数据以更新用户档案"""
        profile = self.user_profiles[user_id]
        
        # 分析通信风格
        query = interaction_data.get('query', '')
        if len(query) < 20:
            profile['communication_style'] = 'concise'
        elif '?' in query and len(query.split()) > 10:
            profile['communication_style'] = 'detailed'
        
        # 分析偏好的主题
        topic = interaction_data.get('topic_category', 'general')
        if topic not in profile['preferred_topics']:
            profile['preferred_topics'].append(topic)
        
        # 分析响应时间模式
        timestamp = interaction_data.get('timestamp', datetime.now().isoformat())
        hour = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).hour
        if 'hours_active' not in profile['response_timing']:
            profile['response_timing']['hours_active'] = {}
        profile['response_timing']['hours_active'][str(hour)] = \
            profile['response_timing']['hours_active'].get(str(hour), 0) + 1
    
    def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """获取用户档案"""
        return self.user_profiles.get(user_id, {})
    
    def get_interaction_patterns(self, user_id: str) -> Dict[str, Any]:
        """获取用户交互模式"""
        profile = self.user_profiles.get(user_id, {})
        
        patterns = {
            'most_active_hour': self._get_most_active_hour(profile),
            'preferred_communication_style': profile.get('communication_style', 'neutral'),
            'top_topics': profile.get('preferred_topics', [])[:5],
            'response_preference': self._infer_response_preference(profile)
        }
        
        return patterns
    
    def _get_most_active_hour(self, profile: Dict[str, Any]) -> Optional[int]:
        """获取用户最活跃的小时"""
        timing = profile.get('response_timing', {}).get('hours_active', {})
        if timing:
            return int(max(timing, key=timing.get))
        return None
    
    def _infer_response_preference(self, profile: Dict[str, Any]) -> str:
        """推断用户响应偏好"""
        style = profile.get('communication_style', 'neutral')
        count = profile.get('interaction_count', 0)
        
        if count < 5:
            return 'guided_exploration'  # 新用户需要引导
        elif style == 'concise':
            return 'brief_direct'
        elif style == 'detailed':
            return 'comprehensive'
        else:
            return 'balanced'


# ==================== Nightly Integration Mechanism ====================

class NightlyIntegrationScheduler:
    """
    夜间整合调度系统
    在用户空闲时段自动执行整合操作
    """
    
    def __init__(self, agi_system, storage_path: Path, global_config: Optional[Dict] = None):
        """
        初始化夜间整合调度器
        
        Args:
            agi_system: AGI系统实例
            storage_path: 存储路径
            global_config: 全局配置字典
        """
        self.agi_system = agi_system
        self.storage_path = storage_path
        self.global_config = global_config
        
        # 从全局配置获取参数
        if global_config and "agi_growth" in global_config:
            agi_cfg = global_config["agi_growth"]
            scheduler_cfg = agi_cfg.get("nightly_scheduler", {})
            
            self.enabled = scheduler_cfg.get("enabled", True)
            self.integration_time = scheduler_cfg.get("integration_time", "02:00")
            self.graceful_shutdown_timeout = scheduler_cfg.get("graceful_shutdown_timeout", 30)
            self.retry_attempts = scheduler_cfg.get("retry_attempts", 3)
            self.retry_delay_seconds = scheduler_cfg.get("retry_delay_seconds", 10)
        else:
            self.enabled = True
            self.integration_time = "02:00"
            self.graceful_shutdown_timeout = 30
            self.retry_attempts = 3
            self.retry_delay_seconds = 10
        
        self.scheduler_path = storage_path / "scheduler"
        self.scheduler_path.mkdir(parents=True, exist_ok=True)
        
        self.integration_log = []
        self.last_run = None
        self.is_running = False
        self.shutdown_event = threading.Event()
        
        # 加载上次运行状态
        self._load_scheduler_state()
    
    def _load_scheduler_state(self):
        """加载调度器状态"""
        state_file = self.scheduler_path / "scheduler_state.json"
        if state_file.exists():
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                self.last_run = datetime.fromisoformat(state.get('last_run')) if state.get('last_run') else None
            except Exception as e:
                logging.warning(f"Failed to load scheduler state: {e}")
    
    def save_scheduler_state(self):
        """保存调度器状态"""
        state = {
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'integration_log': self.integration_log[-50:]  # 只保存最近50条记录
        }
        
        state_file = self.scheduler_path / "scheduler_state.json"
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    
    def start_scheduler(self, integration_time: str = "02:00"):
        """
        启动调度器
        
        Args:
            integration_time: 整合执行时间 (HH:MM格式)
        """
        self.is_running = True
        scheduler_thread = threading.Thread(target=self._scheduler_loop, args=(integration_time,))
        scheduler_thread.daemon = True
        scheduler_thread.start()
    
    def stop_scheduler(self):
        """停止调度器"""
        self.is_running = False
        self.shutdown_event.set()
    
    def _scheduler_loop(self, integration_time: str):
        """调度器主循环"""
        while self.is_running and not self.shutdown_event.is_set():
            try:
                # 计算下次运行时间
                next_run = self._calculate_next_run_time(integration_time)
                
                # 等待到运行时间
                sleep_duration = (next_run - datetime.now()).total_seconds()
                if sleep_duration > 0:
                    # 等待期间分段检查退出信号
                    total_wait = sleep_duration
                    while total_wait > 0 and self.is_running and not self.shutdown_event.is_set():
                        wait_chunk = min(60, total_wait)  # 每分钟检查一次
                        time.sleep(wait_chunk)
                        total_wait -= wait_chunk
                
                if not self.is_running or self.shutdown_event.is_set():
                    break
                
                # 执行整合
                self._perform_integration()
                
                # 更新最后运行时间
                self.last_run = datetime.now()
                self.save_scheduler_state()
                
                # 额外等待一段时间避免重复执行
                time.sleep(60)
                
            except Exception as e:
                logging.error(f"Scheduler error: {e}")
                time.sleep(60)  # 出错后稍等再继续
    
    def _calculate_next_run_time(self, time_str: str) -> datetime:
        """计算下次运行时间"""
        hour, minute = map(int, time_str.split(':'))
        now = datetime.now()
        
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # 如果已经过了今天的运行时间，则安排到明天
        if next_run <= now:
            next_run += timedelta(days=1)
        
        return next_run
    
    def _perform_integration(self):
        """执行整合操作"""
        try:
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'operation': 'nightly_integration',
                'status': 'started',
                'details': {}
            }
            
            # 1. 分析当日所有用户交互数据
            daily_data = self._analyze_daily_interactions()
            log_entry['details']['analyzed_interactions'] = len(daily_data.get('interactions', []))
            
            # 2. 更新用户行为模型和偏好配置文件
            self._update_user_models()
            log_entry['details']['updated_user_models'] = True
            
            # 3. 优化AGI成长参数
            self._optimize_agi_parameters()
            log_entry['details']['optimized_parameters'] = True
            
            # 4. 生成成长报告并持久化存储
            report = self._generate_growth_report(daily_data)
            self._store_growth_report(report)
            log_entry['details']['growth_report_generated'] = True
            
            # 5. 备份重要数据并清理临时文件
            self._backup_important_data()
            self._cleanup_temp_files()
            log_entry['details']['backup_and_cleanup'] = True
            
            log_entry['status'] = 'completed'
            log_entry['duration'] = (datetime.now() - datetime.fromisoformat(log_entry['timestamp'])).total_seconds()
            
        except Exception as e:
            log_entry['status'] = 'failed'
            log_entry['error'] = str(e)
            logging.error(f"Integration failed: {e}")
        
        self.integration_log.append(log_entry)
    
    def _analyze_daily_interactions(self) -> Dict[str, Any]:
        """分析当日交互数据"""
        # 这里需要访问交互采样器的数据
        # 简化实现：返回模拟数据
        return {
            'interactions': [],  # 实际应用中从UserInteractionSampler获取
            'learnings': [],
            'conflicts': [],
            'cleanup_candidates': []
        }
    
    def _update_user_models(self):
        """更新用户行为模型"""
        # 更新用户档案和行为模式
        pass
    
    def _optimize_agi_parameters(self):
        """优化AGI成长参数"""
        # 根据历史表现调整参数
        pass
    
    def _generate_growth_report(self, daily_data: Dict[str, Any]) -> Dict[str, Any]:
        """生成成长报告"""
        return {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'summary': 'Daily growth report',
            'metrics': {
                'interactions_processed': len(daily_data.get('interactions', [])),
                'learnings_integrated': len(daily_data.get('learnings', [])),
                'patterns_identified': 0
            }
        }
    
    def _store_growth_report(self, report: Dict[str, Any]):
        """存储成长报告"""
        report_file = self.scheduler_path / f"growth_report_{report['date']}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    
    def _backup_important_data(self):
        """备份重要数据"""
        # 实现数据备份逻辑
        pass
    
    def _cleanup_temp_files(self):
        """清理临时文件"""
        # 清理过期的临时文件
        pass


# ==================== Progressive Development Engine ====================

class ProgressiveDevelopmentEngine:
    """
    渐进式发展引擎
    使系统能够基于交互数据持续优化响应策略
    """
    
    def __init__(self, agi_system, storage_path: Path, global_config: Optional[Dict] = None):
        """
        初始化发展引擎
        
        Args:
            agi_system: AGI系统实例
            storage_path: 存储路径
            global_config: 全局配置字典
        """
        self.agi_system = agi_system
        self.storage_path = storage_path
        self.global_config = global_config
        
        # 从全局配置获取参数
        if global_config and "agi_growth" in global_config:
            agi_cfg = global_config["agi_growth"]
            dev_cfg = agi_cfg.get("progressive_development_engine", {})
            
            self.learning_rate = dev_cfg.get("learning_rate", 0.1)
            self.performance_evaluation_window = dev_cfg.get("performance_evaluation_window", 50)
            self.improvement_threshold = dev_cfg.get("improvement_threshold", 0.1)
            self.adaptation_frequency = dev_cfg.get("adaptation_frequency", 10)
            self.evolution_enabled = dev_cfg.get("evolution_enabled", True)
        else:
            self.learning_rate = 0.1
            self.performance_evaluation_window = 50
            self.improvement_threshold = 0.1
            self.adaptation_frequency = 10
            self.evolution_enabled = True
        
        self.engine_path = storage_path / "development"
        self.engine_path.mkdir(parents=True, exist_ok=True)
        
        self.performance_history = []
        self.adaptation_strategies = {}
        
        self._load_engine_state()
    
    def _load_engine_state(self):
        """加载引擎状态"""
        state_file = self.engine_path / "engine_state.json"
        if state_file.exists():
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                self.performance_history = state.get('performance_history', [])
                self.adaptation_strategies = state.get('adaptation_strategies', {})
            except Exception as e:
                logging.warning(f"Failed to load engine state: {e}")
    
    def save_engine_state(self):
        """保存引擎状态"""
        state = {
            'performance_history': self.performance_history[-100:],  # 只保存最近100条
            'adaptation_strategies': self.adaptation_strategies,
            'last_updated': datetime.now().isoformat()
        }
        
        state_file = self.engine_path / "engine_state.json"
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    
    def evaluate_performance(self, interaction_result: Dict[str, Any]) -> float:
        """
        评估交互性能
        
        Args:
            interaction_result: 交互结果
            
        Returns:
            性能评分 (0-1)
        """
        score = 0.5  # 基础分数
        
        # 根据不同指标调整分数
        if interaction_result.get('satisfaction_score'):
            score = interaction_result['satisfaction_score']
        elif interaction_result.get('followup_questions', 0) < 2:
            # 如果用户没有提出后续问题，可能表示回答不够完整
            score -= 0.1
        elif interaction_result.get('response_length', 0) < 50:
            # 如果响应太短，可能不够详细
            score -= 0.05
        
        # 根据用户反馈调整
        feedback = interaction_result.get('user_feedback', '')
        if 'helpful' in feedback.lower() or 'good' in feedback.lower():
            score = min(1.0, score + 0.2)
        elif 'not helpful' in feedback.lower() or 'confusing' in feedback.lower():
            score = max(0.0, score - 0.3)
        
        return max(0.0, min(1.0, score))
    
    def adapt_based_on_experience(self, interaction_data: Dict[str, Any], performance_score: float):
        """
        基于经验进行适应
        
        Args:
            interaction_data: 交互数据
            performance_score: 性能评分
        """
        # 记录性能历史
        self.performance_history.append({
            'timestamp': datetime.now().isoformat(),
            'interaction_type': interaction_data.get('type', 'unknown'),
            'query_category': interaction_data.get('category', 'general'),
            'performance_score': performance_score,
            'context': {
                'energy_level': self.agi_system.state_layer.energy_level if hasattr(self.agi_system, 'state_layer') else 0.5,
                'mood': self.agi_system.state_layer.mood if hasattr(self.agi_system, 'state_layer') else 0.5,
                'user_profile': interaction_data.get('user_profile', {})
            }
        })
        
        # 根据性能调整策略
        if performance_score < 0.5:
            # 表现不佳时，调整策略
            self._adjust_strategy_for_low_performance(interaction_data, performance_score)
        elif performance_score > 0.8:
            # 表现良好时，强化成功策略
            self._reinforce_successful_strategy(interaction_data)
        
        # 限制历史记录大小
        if len(self.performance_history) > 1000:
            self.performance_history = self.performance_history[-1000:]
        
        # 保存状态
        self.save_engine_state()
    
    def _adjust_strategy_for_low_performance(self, interaction_data: Dict[str, Any], score: float):
        """为低性能调整策略"""
        category = interaction_data.get('category', 'general')
        
        # 增加对该类别的关注
        if category not in self.adaptation_strategies:
            self.adaptation_strategies[category] = {
                'attempts': 0,
                'success_count': 0,
                'avg_performance': 0.5,
                'adjustments': []
            }
        
        strategy = self.adaptation_strategies[category]
        strategy['attempts'] += 1
        strategy['avg_performance'] = (strategy['avg_performance'] * (strategy['attempts'] - 1) + score) / strategy['attempts']
        
        # 记录调整
        adjustment = {
            'timestamp': datetime.now().isoformat(),
            'type': 'performance_correction',
            'previous_score': score,
            'adjustment_made': 'increased_attention_to_category'
        }
        strategy['adjustments'].append(adjustment)
    
    def _reinforce_successful_strategy(self, interaction_data: Dict[str, Any]):
        """强化成功策略"""
        category = interaction_data.get('category', 'general')
        
        if category in self.adaptation_strategies:
            strategy = self.adaptation_strategies[category]
            strategy['success_count'] += 1
            strategy['attempts'] += 1
            
            # 记录成功
            adjustment = {
                'timestamp': datetime.now().isoformat(),
                'type': 'success_reinforcement',
                'adjustment_made': 'maintained_current_approach'
            }
            strategy['adjustments'].append(adjustment)
    
    def suggest_improvements(self) -> List[str]:
        """建议改进措施"""
        improvements = []
        
        # 分析性能历史找出需要改进的领域
        if len(self.performance_history) > 10:
            # 计算各类别的平均性能
            category_performance = defaultdict(list)
            for record in self.performance_history[-50:]:  # 最近50条记录
                cat = record.get('query_category', 'general')
                category_performance[cat].append(record['performance_score'])
            
            for category, scores in category_performance.items():
                avg_score = sum(scores) / len(scores)
                if avg_score < 0.6:  # 平均分数低于0.6的类别需要改进
                    improvements.append(f"Improve performance for '{category}' queries (current avg: {avg_score:.2f})")
        
        return improvements
    
    def evolve_personality_traits(self):
        """演进个性特质"""
        # 根据交互历史调整个性特质
        if not hasattr(self.agi_system, 'dna_layer'):
            return
        
        # 分析交互历史中的模式
        if len(self.performance_history) > 20:
            # 计算某些特质的调整方向
            helpful_interactions = [r for r in self.performance_history if r['performance_score'] > 0.7]
            
            if len(helpful_interactions) > len(self.performance_history) * 0.6:
                # 如果大部分交互都很成功，可以稍微提高自信度
                current_empathy = self.agi_system.dna_layer.get_trait('capabilities', 'empathy')
                self.agi_system.dna_layer.capabilities['empathy'] = min(1.0, current_empathy + 0.05)
        
        # 保存DNA变化
        dna_config_path = self.storage_path / "dna_config.json"
        self.agi_system.dna_layer.save_config(dna_config_path)


# ==================== AGI Growth System Integration ====================

class AGIGrowthSystem:
    """
    AGI成长系统整合类
    将所有组件整合在一起
    """
    
    def __init__(self, workspace_path: Path, config_path: Optional[Path] = None):
        """
        初始化AGI成长系统
        
        Args:
            workspace_path: 工作空间路径
            config_path: 配置文件路径（可选，默认为workspace_path下的agi_config.json）
        """
        self.workspace_path = workspace_path
        self.storage_path = workspace_path / ".agi_growth"
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # 加载全局配置
        self.global_config = self._load_global_config(config_path or (workspace_path / "agi_config.json"))
        
        # 初始化五层架构
        self.dna_layer = DNALayer(
            config_path=self.storage_path / "dna_config.json",
            global_config=self.global_config
        )
        self.soul_layer = SoulLayer(
            self.storage_path / "soul_memory",
            global_config=self.global_config
        )
        self.state_layer = StateLayer(global_config=self.global_config)
        
        # 初始化推理层
        self.inference_layer = InferenceLayer(
            self.dna_layer,
            self.soul_layer,
            self.state_layer,
            global_config=self.global_config
        )
        
        # 初始化整合层
        self.consolidation_layer = ConsolidationLayer(
            self.soul_layer,
            self.storage_path / "consolidation",
            global_config=self.global_config
        )
        
        # 初始化用户交互采样器
        self.interaction_sampler = UserInteractionSampler(
            self.storage_path / "user_data",
            global_config=self.global_config
        )
        
        # 初始化夜间整合调度器
        self.nightly_scheduler = NightlyIntegrationScheduler(
            self,
            self.storage_path,
            global_config=self.global_config
        )
        
        # 初始化渐进式发展引擎
        self.development_engine = ProgressiveDevelopmentEngine(
            self,
            self.storage_path,
            global_config=self.global_config
        )
    
    def _load_global_config(self, config_path: Path) -> Dict[str, Any]:
        """加载全局配置"""
        if config_path and config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logging.warning(f"Failed to load global config from {config_path}: {e}")
                return {}
        return {}
    
    def process_interaction(self, user_id: str, query: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        处理用户交互
        
        Args:
            user_id: 用户ID
            query: 用户查询
            context: 上下文信息
            
        Returns:
            处理结果
        """
        # 记录开始时间
        start_time = datetime.now()
        
        # 使用推理层生成响应
        result = self.inference_layer.make_decision(query, context)
        
        # 更新状态
        self.state_layer.update_after_interaction()
        
        # 记录交互到采样器
        interaction_data = {
            'user_id': user_id,
            'query': query,
            'response': result.get('response', ''),
            'confidence': result.get('confidence', 0.5),
            'processing_time': (datetime.now() - start_time).total_seconds(),
            'context': context or {}
        }
        
        self.interaction_sampler.record_interaction(user_id, interaction_data)
        
        # 评估性能并适应
        performance_score = self.development_engine.evaluate_performance({
            'response': result.get('response', ''),
            'confidence': result.get('confidence', 0.5),
            'processing_time': interaction_data['processing_time']
        })
        
        self.development_engine.adapt_based_on_experience(interaction_data, performance_score)
        
        return result
    
    def trigger_daily_consolidation(self, force: bool = False) -> Dict[str, Any]:
        """
        触发日常整合
        
        Args:
            force: 是否强制执行
            
        Returns:
            整合结果
        """
        # 收集当日数据
        daily_data = {
            'interactions': self.interaction_sampler.interactions_log[-100:],  # 最近100次交互
            'learnings': [],  # 从发展引擎获取学习
            'conflicts': [],  # 从系统中检测冲突
            'cleanup_candidates': []  # 待清理项目
        }
        
        # 执行整合
        report = self.consolidation_layer.daily_consolidation(daily_data)
        
        # 保存采样器数据
        self.interaction_sampler.save_to_storage()
        
        # 保存灵魂层数据
        self.soul_layer.save_to_storage()
        
        return report
    
    def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """获取用户档案"""
        return self.interaction_sampler.get_user_profile(user_id)
    
    def get_growth_metrics(self) -> Dict[str, Any]:
        """获取成长指标"""
        return {
            'total_interactions': len(self.interaction_sampler.interactions_log),
            'unique_users': len(self.interaction_sampler.user_profiles),
            'soul_memory_size': len(self.soul_layer.experiences) + len(self.soul_layer.cognitions),
            'development_suggestions': self.development_engine.suggest_improvements(),
            'last_consolidation': getattr(self.consolidation_layer, 'last_consolidation', None)
        }
    
    def start_nightly_scheduler(self, integration_time: str = "02:00"):
        """启动夜间调度器"""
        self.nightly_scheduler.start_scheduler(integration_time)
    
    def stop_nightly_scheduler(self):
        """停止夜间调度器"""
        self.nightly_scheduler.stop_scheduler()