import React from 'react';
import PendingActivityMatcher from './PendingActivityMatcher.jsx';

export default function PendingSurveyMatcher(props){
  return <PendingActivityMatcher {...props} kind="surveys"/>;
}
