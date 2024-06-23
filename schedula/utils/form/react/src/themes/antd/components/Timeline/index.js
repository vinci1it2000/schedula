import {Timeline as BaseTimeline} from 'antd';

const Timeline = ({children, render, ...props}) => (
    <BaseTimeline {...props}>
        {children}
    </BaseTimeline>);
export default Timeline;