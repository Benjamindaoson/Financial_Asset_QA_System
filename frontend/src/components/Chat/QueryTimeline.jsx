import React from 'react';
import { CheckCircle, Circle, Loader } from 'lucide-react';

const QueryTimeline = ({ events = [], loading = false }) => {
  // Filter events to show only key steps
  const keyEvents = events.filter(event =>
    ['model_selected', 'tool_start', 'analysis_chunk'].includes(event.type)
  );

  // Map tool names to display text
  const toolDisplayMap = {
    'search_knowledge': '📚 知识库检索',
    'get_price': '📊 获取实时价格',
    'get_financial_data': '💰 财务数据获取',
    'calculate_ratio': '🧮 财务比率计算',
    'analyze_trend': '📈 趋势分析',
    'compare_stocks': '⚖️ 股票对比',
    'default': '🔧 工具调用'
  };

  const getDisplayText = (event) => {
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

  // Limit display to avoid clutter - show first 2 + ... + last 1
  const maxSteps = 3;
  let displayEvents = keyEvents;
  let showEllipsis = false;

  if (keyEvents.length > maxSteps) {
    displayEvents = [
      ...keyEvents.slice(0, 2),
      keyEvents[keyEvents.length - 1]
    ];
    showEllipsis = true;
  }

  if (keyEvents.length === 0 && !loading) {
    return null;
  }

  return (
    <div className="mb-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
      {/* Desktop: Horizontal timeline */}
      <div className="hidden md:flex items-center justify-start space-x-2">
        {displayEvents.map((event, index) => {
          const isLast = index === displayEvents.length - 1;
          const isActuallyLast = index === keyEvents.length - 1;
          return (
            <React.Fragment key={index}>
              {showEllipsis && index === 2 && (
                <>
                  <div className="flex items-center space-x-2 text-gray-400">
                    <span className="text-sm">...</span>
                  </div>
                  <div className="flex-shrink-0 w-8 h-0.5 bg-gray-300" />
                </>
              )}
              <div className="flex items-center space-x-2">
                {getStatusIcon(isActuallyLast ? keyEvents.length - 1 : index, isActuallyLast)}
                <span className={`text-sm ${
                  isActuallyLast && loading ? 'text-blue-600 font-medium' : 'text-gray-700'
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
      </div>

      {/* Mobile: Vertical timeline */}
      <div className="md:hidden space-y-3">
        {displayEvents.map((event, index) => {
          const isLast = index === displayEvents.length - 1;
          const isActuallyLast = index === keyEvents.length - 1;
          return (
            <React.Fragment key={index}>
              {showEllipsis && index === 2 && (
                <div className="flex items-start space-x-3 text-gray-400">
                  <Circle className="w-5 h-5" />
                  <span className="text-sm pt-0.5">...</span>
                </div>
              )}
              <div className="flex items-start space-x-3">
                <div className="flex flex-col items-center">
                  {getStatusIcon(isActuallyLast ? keyEvents.length - 1 : index, isActuallyLast)}
                  {!isLast && (
                    <div className="w-0.5 h-8 bg-gray-300 mt-1" />
                  )}
                </div>
                <div className={`text-sm pt-0.5 ${
                  isActuallyLast && loading ? 'text-blue-600 font-medium' : 'text-gray-700'
                }`}>
                  {getDisplayText(event)}
                </div>
              </div>
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
};

export default QueryTimeline;
