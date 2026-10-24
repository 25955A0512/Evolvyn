import type { StudioTab } from './components/AgentWorkspace';
export const studioRoutes:Record<string,StudioTab>={ '/product-studio':'build','/discussionroom':'discuss','/keyvault':'vault','/integrations':'integrations','/canvas':'canvas','/growth':'growth','/agents':'agents','/agent-memory':'memory','/runtime':'runtime'};
export const panelRoutes:Record<string,'automation'|'workflow'|'account'|'tasks'|'reports'|'projects'>={'/monitoring':'automation','/workflows':'workflow','/team-settings':'account','/tasks':'tasks','/reports':'reports','/projects':'projects'};
export const validRoutes=new Set(['/', '/login','/signup','/auth/callback','/dashboard','/mcp-registry','/audit-logs',...Object.keys(studioRoutes),...Object.keys(panelRoutes)]);
export function pathForStudio(tab:StudioTab|null){return tab?Object.entries(studioRoutes).find(([,value])=>value===tab)?.[0]||'/dashboard':'/dashboard';}
export function pathForPanel(panel:string|null){return panel?Object.entries(panelRoutes).find(([,value])=>value===panel)?.[0]||'/dashboard':'/dashboard';}
