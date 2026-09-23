"""默认经济前后对照；期望点数流量，不将掉卡/重复碎片当作保底收益。"""
import copy
import json
from pathlib import Path
import tomllib

"""上一版（v3）经济与规则，用于前后对照。"""
OLD={'economy':{'min_reward':60,'max_reward':100,'streak_daily_step':5,'streak_daily_max':40,
 'streak_weekly_reward':200,'streak_cycle_reward':400,'savings_bonus_1':50,'savings_bonus_2':150,'savings_bonus_3':500},
 'task':{'normal_count':3,'challenge_count':2,'normal_reward':30,'challenge_reward_s':50,'challenge_reward_ss':65,'challenge_reward_sss':80,'ultimate_reward':30000},
 'monthly_card':{'daily_bonus':70}}
OLD_RULES={'checkin_small_gifts':1,'checkin_fragments':2,'weekly_fragments':10,
 'monthly_event_days':0,'monthly_event_fragments':0,'monthly_event_small_gift_days':[],
 'monthly_event_medium_gift_days':[],'monthly_event_large_gift_days':[],
 'companion_points':300,'gift_points':{'small':300,'medium':1000,'large':10000},
 'task_medium_gifts_daily_cap':1,'task_medium_gift_sources':['challenge'],
 'task_fragments_daily_cap':4,'task_fragments':{'normal':1,'challenge':2,'ultimate':0},
 'bloom_levels':[50,100],'bloom_costs':[30,90],'ultimate_large_gifts_lifetime_cap':0}

def build(root):
    current=tomllib.loads((root/'config.toml').read_text(encoding='utf8'))
    old=copy.deepcopy(current)
    for section,values in OLD.items():old[section].update(values)
    rules=json.loads((root/'assets/growth/rules_draft.json').read_text(encoding='utf8'))
    curve=json.loads((root/'assets/growth/affection_curve.json').read_text(encoding='utf8'))['thresholds']
    rows=[]
    for version,config,rules in [('before',old,OLD_RULES),('after',current,rules)]:
        ec=config['economy'];task=config['task']
        small_days=set(rules.get('monthly_event_small_gift_days') or [])
        medium_days=set(rules.get('monthly_event_medium_gift_days') or [])
        large_days=set(rules.get('monthly_event_large_gift_days') or [])
        for profile,n,c in [('签到陪伴',0,0),('每日1普通',1,0),('每日1普通1挑战SSS',1,1),('每日完成全部普通与挑战SSS',task['normal_count'],task['challenge_count'])]:
            points=affection=fragments=small=medium=large=0;milestones={};totals={};stage=0
            for day in range(1,1001):
                points+=(ec['min_reward']+ec['max_reward'])/2+min((day-1)*ec['streak_daily_step'],ec['streak_daily_max'])
                points+=ec['streak_weekly_reward'] if day%7==0 else 0
                points+=ec['streak_cycle_reward'] if day%ec['streak_cycle_days']==0 else 0
                points+=n*task['normal_reward']+c*task['challenge_reward_sss']
                day_of_month=(day-1)%30+1
                in_event=day_of_month<=rules.get('monthly_event_days',0)
                gift_small=int(in_event and day_of_month in small_days)
                gift_medium=int(in_event and day_of_month in medium_days)
                gift_large=int(in_event and day_of_month in large_days)
                if not in_event:
                    gift_small=rules.get('checkin_small_gifts',0)
                    fragments+=rules.get('checkin_fragments',0)+(rules.get('weekly_fragments',0) if day%7==0 else 0)
                elif day_of_month not in small_days|medium_days|large_days:
                    fragments+=rules['monthly_event_fragments']
                small+=gift_small;medium+=gift_medium;large+=gift_large
                task_gifts=min(rules['task_medium_gifts_daily_cap'],int(c>0))
                medium+=task_gifts
                affection=min(curve[-1],affection+rules['companion_points']
                              +gift_small*rules['gift_points']['small']
                              +gift_medium*rules['gift_points']['medium']
                              +gift_large*rules['gift_points']['large']
                              +task_gifts*rules['gift_points']['medium'])
                fragments+=min(rules['task_fragments_daily_cap'],n*rules['task_fragments']['normal']+c*rules['task_fragments']['challenge'])
                for level in (50,100,1000):
                    if affection>=curve[level]:milestones.setdefault(f'level_{level}',day)
                while stage<2 and fragments>=rules['bloom_costs'][stage] and affection>=curve[rules['bloom_levels'][stage]]:
                    fragments-=rules['bloom_costs'][stage];stage+=1;milestones[f'full_star_stage_{stage}']=day
                if day in (30,90):totals[day]={'points':points,'eleven_pull_equivalent':round(points/ec['cost_11'],2),
                  'small_gifts':small,'medium_gifts':medium,'large_gifts':large,'fragments':fragments,'stage':stage}
            rows.append({'version':version,'profile':profile,'totals':totals,'milestones':milestones})
    return {'assumptions':['从第1天连续签到；已拥有并集中培养一个主角色，每日陪伴，礼物用于同一角色。',
      '基础签到按数学期望；挑战按SSS上界；无月卡、囤点奖、终极奖、管理员注入。',
      '十一连等价仅为点数/500，不是抽到目标卡或满星概率。阶段时间假设目标卡预先满星。',
      '未计5%签到掉卡及随机抽卡重复碎片，所得养成时间仅隔离固定奖励通道。',
      '保留极低概率签到彩蛋点数，数学期望约0.145点/天；未计入本表。',
      '满级后的礼物数量为累计发放量，不表示全部已消费。'],
      'changes':{'before':OLD,'after':{s:{k:current[s][k] for k in v} for s,v in OLD.items()}},
      'monthly_card':{
        'price':current['monthly_card']['price'],'days':current['monthly_card']['duration_days'],
        'bonus_before':OLD['monthly_card']['daily_bonus']*current['monthly_card']['duration_days'],
        'bonus_after':current['monthly_card']['daily_bonus']*current['monthly_card']['duration_days'],
        'net_after':current['monthly_card']['daily_bonus']*current['monthly_card']['duration_days']-current['monthly_card']['price'],
        'two_half_price_coupon_savings':250},
      'savings_max_per_60_days':{
        'before':sum(OLD['economy'][f'savings_bonus_{i}'] for i in (1,2,3)),
        'after':sum(current['economy'][f'savings_bonus_{i}'] for i in (1,2,3))},'rows':rows}

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();report=build(Path(__file__).parent)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    for row in report['rows']:
        print(row['version'],row['profile'].encode('unicode_escape').decode(),row['totals'][30],row['milestones'])
