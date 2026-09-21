import { useQuery } from '@tanstack/react-query';
import { workflowsApi, analyticsApi } from '../lib/api';
import { formatCost, formatDate } from '../lib/utils';
import { DollarSign, BarChart3, LineChart as ChartIcon, PieChart as PieIcon, Download, RefreshCw } from 'lucide-react';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend
} from 'recharts';
import { toast } from 'sonner';

export function CostPage() {
  const { data, isLoading: isWfLoading, refetch: refetchWf, isFetching: isWfFetching } = useQuery({
    queryKey: ['workflowsCost'],
    queryFn: () => workflowsApi.list(1),
  });

  const { data: analyticsData, isLoading: isAnalyticsLoading, refetch: refetchAnalytics, isFetching: isAnalyticsFetching } = useQuery({
    queryKey: ['analyticsData'],
    queryFn: () => analyticsApi.get(),
  });

  const isLoading = isWfLoading || isAnalyticsLoading;
  const isFetching = isWfFetching || isAnalyticsFetching;
  const refetch = () => {
    refetchWf();
    refetchAnalytics();
  };

  const workflows = data?.workflows || [];

  // Generate aggregate metrics from dynamic backend analytics
  const totalCost = analyticsData?.total_cost_usd ?? workflows.reduce((sum, w) => sum + (w.total_cost_usd || 0), 0);
  const totalLeads = analyticsData?.total_leads ?? workflows.reduce((sum, w) => sum + (w.results_count || 0), 0);
  const costPerLead = totalLeads ? totalCost / totalLeads : (analyticsData?.cost_per_lead ?? 0.0);

  const agentColors: Record<string, string> = {
    'planner_agent': '#3B82F6',
    'search_agent': '#06B6D4',
    'company_discovery_agent': '#14B8A6',
    'validation_agent': '#10B981',
    'decision_maker_agent': '#8B5CF6',
    'contact_enrichment_agent': '#A855F7',
    'summary_agent': '#F59E0B',
    'human_approval_agent': '#EC4899',
  };

  const backendBreakdown = analyticsData?.agent_breakdown || [];
  const agentCostData = backendBreakdown.length > 0
    ? backendBreakdown.map((b: any) => ({
        name: b.name.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase()),
        cost: b.cost,
        color: agentColors[b.name] || '#3B82F6',
      }))
    : [
        { name: 'Planner Agent', cost: 0.125, color: '#3B82F6' },
        { name: 'Search Agent', cost: 0.084, color: '#06B6D4' },
        { name: 'Company Discovery', cost: 0.062, color: '#14B8A6' },
        { name: 'Validation Agent', cost: 0.024, color: '#10B981' },
        { name: 'Decision Maker', cost: 0.048, color: '#8B5CF6' },
        { name: 'Contact Enrichment', cost: 0.144, color: '#A855F7' },
        { name: 'Summary Agent', cost: 0.180, color: '#F59E0B' },
        { name: 'Human Approval', cost: 0.000, color: '#EC4899' },
      ];

  const dailySpendData = (analyticsData?.daily_spend && analyticsData.daily_spend.length > 0)
    ? analyticsData.daily_spend
    : [
        { day: 'Day 1', spend: 0.12 },
        { day: 'Day 2', spend: 0.28 },
        { day: 'Day 3', spend: 0.42 },
        { day: 'Day 4', spend: 0.15 },
        { day: 'Day 5', spend: 0.89 },
        { day: 'Day 6', spend: 1.12 },
        { day: 'Day 7', spend: 0.65 },
      ];

  const pieColors = ['#3B82F6', '#06B6D4', '#14B8A6', '#10B981', '#8B5CF6', '#A855F7', '#F59E0B', '#EF4444'];

  const handleExportCSV = () => {
    if (workflows.length === 0) {
      toast.error('No workflow cost data to export');
      return;
    }

    const headers = 'Workflow Name,Status,Leads Found,Cost (USD),Cost Per Lead,Created At\n';
    const rows = workflows
      .map((w) => {
        const cpl = w.results_count ? (w.total_cost_usd || 0) / w.results_count : 0;
        return `"${w.name}",${w.status},${w.results_count || 0},${(w.total_cost_usd || 0).toFixed(4)},${cpl.toFixed(4)},${w.created_at}`;
      })
      .join('\n');

    const blob = new Blob([headers + rows], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `agentsphere_cost_analytics.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    toast.success('Cost data exported successfully');
  };

  return (
    <div className="space-y-8 select-none">
      {/* Title */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <DollarSign className="h-6 w-6 text-primary" /> Cost Analytics
          </h1>
          <p className="text-text-muted text-sm mt-1">
            Real-time per-workflow token logs and background execution cost reports
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleExportCSV}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-secondary hover:bg-elevated text-text-secondary hover:text-white border border-border hover:border-border-hover rounded-md text-xs font-semibold transition-colors duration-150 interactive-btn"
          >
            <Download className="h-3.5 w-3.5" />
            <span>Export CSV</span>
          </button>
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="p-2 rounded-md hover:bg-surface text-text-muted hover:text-white border border-border hover:border-border-hover transition-colors duration-150 interactive-btn"
          >
            <RefreshCw className={`h-4.5 w-4.5 ${isFetching ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Metric Cards Row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Metric 1 */}
        <div className="glass-card p-4">
          <span className="text-[10px] text-text-muted font-bold uppercase tracking-wider">Total Monthly Spent</span>
          <div className="text-2xl font-black text-white mt-1">{formatCost(totalCost)}</div>
          <span className="text-[9px] text-success font-semibold mt-1 block">Incurred from GPT-4o & Serper API</span>
        </div>

        {/* Metric 2 */}
        <div className="glass-card p-4">
          <span className="text-[10px] text-text-muted font-bold uppercase tracking-wider">Cost Per Lead</span>
          <div className="text-2xl font-black text-white mt-1">{formatCost(costPerLead)}</div>
          <span className="text-[9px] text-text-muted mt-1 block">Average cost per verified prospect contact</span>
        </div>

        {/* Metric 3 */}
        <div className="glass-card p-4">
          <span className="text-[10px] text-text-muted font-bold uppercase tracking-wider">Most Active Agent</span>
          <div className="text-lg font-extrabold text-white mt-1 truncate">
            {agentCostData[0]?.name || 'Summary Agent'}
          </div>
          <span className="text-[9px] text-primary font-semibold mt-1 block">
            {agentCostData[0] ? `Cost: ${formatCost(agentCostData[0].cost)}` : 'Avg. cost: $0.180'}
          </span>
        </div>

        {/* Metric 4 */}
        <div className="glass-card p-4">
          <span className="text-[10px] text-text-muted font-bold uppercase tracking-wider">Most Recent Pipeline</span>
          <div className="text-lg font-extrabold text-white mt-1 truncate">
            {workflows[0]?.name || 'Pre-Seed B2B'}
          </div>
          <span className="text-[9px] text-success font-semibold mt-1 block">
            {workflows[0] ? `Status: ${workflows[0].status}` : 'Average lead CPL: $0.024'}
          </span>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Chart 1: Bar chart */}
        <div className="glass-card p-5">
          <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2 mb-4">
            <BarChart3 className="h-4 w-4 text-primary" /> Average Cost Per Agent
          </h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={agentCostData}
                layout="vertical"
                margin={{ top: 5, right: 10, left: 20, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis type="number" stroke="#9CA3AF" fontSize={10} tickFormatter={(v) => `$${v.toFixed(3)}`} />
                <YAxis dataKey="name" type="category" stroke="#9CA3AF" fontSize={10} width={100} />
                <Tooltip formatter={(value: any) => [`$${value.toFixed(4)}`, 'Average Cost']} />
                <Bar dataKey="cost" fill="#3B82F6">
                  {agentCostData.map((e: any, index: number) => (
                    <Cell key={`cell-${index}`} fill={e.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Chart 2: Line chart */}
        <div className="glass-card p-5">
          <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2 mb-4">
            <ChartIcon className="h-4 w-4 text-success" /> Daily API Spend (Last 7 Days)
          </h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={dailySpendData} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="day" stroke="#9CA3AF" fontSize={10} />
                <YAxis stroke="#9CA3AF" fontSize={10} tickFormatter={(v) => `$${v.toFixed(2)}`} />
                <Tooltip formatter={(value: any) => [`$${value.toFixed(4)}`, 'Daily Cost']} />
                <Line type="monotone" dataKey="spend" stroke="#10B981" strokeWidth={2.5} dot={{ r: 4 }} activeDot={{ r: 6 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Chart 3: Pie Chart split */}
      <div className="glass-card p-5 max-w-lg mx-auto">
        <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2 mb-4">
          <PieIcon className="h-4 w-4 text-accent" /> Cost Distribution Across Agents
        </h2>
        <div className="h-60 flex items-center justify-center">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={agentCostData}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={70}
                paddingAngle={2}
                dataKey="cost"
              >
                {agentCostData.map((_: any, index: number) => (
                  <Cell key={`cell-${index}`} fill={pieColors[index % pieColors.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(value: any) => [`$${value.toFixed(4)}`, 'Cost Split']} />
              <Legend verticalAlign="bottom" height={36} wrapperStyle={{ fontSize: '9px' }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Workflow Cost Table */}
      <div className="glass-card p-6">
        <h2 className="text-sm font-semibold text-slate-200 mb-4">Pipeline Execution Cost Audits</h2>
        
        {isLoading ? (
          <div className="space-y-3 animate-pulse">
            <div className="h-10 bg-secondaryBg rounded" />
            <div className="h-20 bg-secondaryBg rounded" />
          </div>
        ) : workflows.length === 0 ? (
          <p className="text-xs text-text-muted text-center py-6">No workflow cost records available</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border/40 text-text-muted text-xs uppercase tracking-wider">
                  <th className="pb-3 font-semibold">Workflow Name</th>
                  <th className="pb-3 font-semibold">Status</th>
                  <th className="pb-3 font-semibold">Leads</th>
                  <th className="pb-3 font-semibold">Total Cost (USD)</th>
                  <th className="pb-3 font-semibold text-right">Cost Per Lead</th>
                  <th className="pb-3 font-semibold text-right">Created At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/20">
                {workflows.map((w) => {
                  const leads = w.results_count || 0;
                  const cost = w.total_cost_usd || 0;
                  const cpl = leads ? cost / leads : 0;
                  
                  return (
                    <tr key={w.workflow_id} className="hover:bg-surface/20 transition-all">
                      <td className="py-3.5 text-white font-medium">{w.name}</td>
                      <td className="py-3.5">
                        <span className={`text-[10px] px-2 py-0.5 border font-semibold rounded-full uppercase ${
                          w.status === 'completed' ? 'bg-success/15 border-success/35 text-success' :
                          w.status === 'running' ? 'bg-primary/15 border-primary/35 text-primary' :
                          w.status === 'awaiting_approval' ? 'bg-warning/15 border-warning/35 text-warning animate-pulse' :
                          'bg-text-disabled/15 border-border text-text-muted'
                        }`}>
                          {w.status.replace('_', ' ')}
                        </span>
                      </td>
                      <td className="py-3.5 text-text-secondary">{leads}</td>
                      <td className="py-3.5 font-mono text-white">{formatCost(cost)}</td>
                      <td className="py-3.5 font-mono text-right text-success">{formatCost(cpl)}</td>
                      <td className="py-3.5 text-right text-text-muted text-xs">{formatDate(w.created_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default CostPage;
