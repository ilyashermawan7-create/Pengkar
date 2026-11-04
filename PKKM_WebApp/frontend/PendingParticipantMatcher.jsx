import React from 'react';
import PendingActivityMatcher from './PendingActivityMatcher.jsx';

export default function PendingParticipantMatcher(props){
  return <PendingActivityMatcher {...props} kind="participants"/>;
}
