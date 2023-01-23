import {Card} from 'antd';

const {Meta: BaseMeta} = Card,
    Meta = ({children, render, ...props}) => (
        <BaseMeta {...props}>
            {children}
        </BaseMeta>);
export default Meta;