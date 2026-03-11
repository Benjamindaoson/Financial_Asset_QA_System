"""
用户反馈组件 - 收集用户对回答的评价
User Feedback Component - Collect user ratings for responses
"""
import { useState } from "react";

export function FeedbackButtons({ messageId, onFeedback }) {
  const [feedback, setFeedback] = useState(null);
  const [submitted, setSubmitted] = useState(false);

  const handleFeedback = async (rating) => {
    setFeedback(rating);
    setSubmitted(true);

    // 发送反馈到后端
    try {
      await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message_id: messageId,
          rating: rating,
          timestamp: new Date().toISOString(),
        }),
      });

      if (onFeedback) {
        onFeedback(rating);
      }
    } catch (error) {
      console.error("Failed to submit feedback:", error);
    }
  };

  if (submitted) {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-500 mt-2">
        <span>感谢您的反馈！</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 mt-2">
      <span className="text-sm text-gray-500">这个回答有帮助吗？</span>
      <button
        onClick={() => handleFeedback("positive")}
        className="p-1 hover:bg-gray-100 rounded transition-colors"
        title="有帮助"
      >
        👍
      </button>
      <button
        onClick={() => handleFeedback("negative")}
        className="p-1 hover:bg-gray-100 rounded transition-colors"
        title="没帮助"
      >
        👎
      </button>
    </div>
  );
}
