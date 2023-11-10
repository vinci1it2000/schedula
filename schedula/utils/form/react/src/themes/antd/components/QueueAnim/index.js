import BaseQueueAnim from 'rc-queue-anim';

const QueueAnim = ({children, render, ...props}) => (
    <BaseQueueAnim {...props}>
        {children}
    </BaseQueueAnim>);
export default QueueAnim;