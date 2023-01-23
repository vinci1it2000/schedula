import {Card as BaseCard} from 'antd';

const Card = ({children, render, ...props}) => (
    <BaseCard {...props}>
        {children}
    </BaseCard>);
export default Card;