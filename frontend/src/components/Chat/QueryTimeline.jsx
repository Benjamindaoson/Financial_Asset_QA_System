import React from 'react';
import { CheckCircle, Circle, Loader } from 'lucide-react';

const QueryTimeline = ({ events = [], loading = false }) => {
  // Filter events to show only key steps
  const keyEvents = events.filter(event =>
    ['model_selected', 'tool_start', 'analysis_chunk'].includes(event.type)
  );

  // Map tool names to display text
  const toolDisplayMap = {
    'search_knowledge_base': '知识库检索',
    'get_stock_info': '股票信息查询',
    'get_financial_data': '财务数据获取',
    'calculate_financial_ratio': '财务比率计算',
    'analyze_trend': '趋势分析',
    'compare_companies': '公司对比',
    'default': '工具调用'
  };

  const getDisplayText = (event) => {
    if (event.type === 'model_selected') {
      return `选择模型: ${event.data?.model || '未知'}`;
    }
    if (event.type === 'tool_start') {
      const toolName = event.data?.tool_name || 'default';
      return toolDisplayMap[toolName] || toolDisplayMap['default'];
    }
    if (event.type === 'analysis_chunk') {
      return '分析中...';
    }
    return event.type;
  };

  const getStatusIcon = (index, isLast) => {
    if (index < keyEvents.length - 1) {
      // Completed step
      return <CheckCircle className="w-5 h-5 text-green-500" />;
    }
    if (isLast && loading) {
      // Current step (in progress)
      return <Loader className="w-5 h-5 text-blue-500 animate-spin" />;
    }
    if (isLast && !loading) {
      // Last step completed
      return <CheckCircle className="w-5 h-5 text-green-500" />;
    }
    // Pending step
    return <Circle className="w-5 h-5 text-gray-300" />;
  };

  // Limit display to avoid clutter
  const maxDisplaySteps = window.innerWidth > 768 ? 5 : 3;
  const displayEvents = keyEvents.slice(0, maxDisplaySteps);
  const hasMore = keyEvents.length > maxDisplaySteps;

  if (keyEvents.length === 0 && !loading) {
    return null;
  }

  return (
    <div className="mb-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
      <div className="text-sm font-medium text-gray-700 mb-3">查询路由过程</div>

      {/* Desktop: Horizontal timeline */}
      <div className="hidden md:flex items-center justify-start space-x-2">
        {displayEvents.map((event, index) => {
          const isLast = index === displayEvents.length - 1;
          return (
            <React.Fragment key={index}>
              <div className="flex items-center space-x-2">
                {getStatusIcon(index, isLast)}
                <span className={`text-sm ${
                  index < keyEvents.length - 1 ? 'text-gray-700' : 'text-blue-600 font-medium'
                }`}>
                  {getDisplayText(event)}
                </span>
              </div>
              {!isLast && (
                <div className="flex-shrink-0 w-8 h-0.5 bg-gray-300" />
              )}
            </React.Fragment>
          );
        })}
        {hasMore && (
          <div className="flex items-center space-x-2 text-gray-400">
            <span className="text-sm">...</span>
          </div>
        )}
      </div>

      {/* Mobile: Vertical timeline */}
      <div className="md:hidden space-y-3">
        {displayEvents.map((event, index) => {
          const isLast = index === displayEvents.length - 1;
          return (
            <div key={index} className="flex items-start space-x-3">
              <div className="flex flex-col items-center">
                {getStatusIcon(index, isLast)}
                {!isLast && (
                  <div className="w-0.5 h-8 bg-gray-300 mt-1" />
                )}
              </div>
              <div className={`text-sm pt-0.5 ${
                index < keyEvents.length - 1 ? 'text-gray-700' : 'text-blue-600 font-medium'
              }`}>
                {getDisplayText(event)}
              </div>
            </div>
          );
        })}
        {hasMore && (
          <div className="flex items-start space-x-3 text-gray-400">
            <Circle className="w-5 h-5" />
            <span className="text-sm pt-0.5">...</span>
          </div>
        )}
      </div>

      {/* Loading indicator */}
      {loading && (
        <div className="mt-3 flex items-center space-x-2 text-blue-600">
          <div className="w-2 h-2 bg-blue-600 rounded-full animate-pulse" />
          <span className="text-xs">处理中...</span>
        </div>
      )}
    </div>
  );
};

export default QueryTimeline;
