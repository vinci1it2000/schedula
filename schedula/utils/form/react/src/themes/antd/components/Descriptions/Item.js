import {Descriptions} from 'antd';

const {Item: BaseItem} = Descriptions,
    Item = ({children, render, ...props}) => (
        <BaseItem {...props}>
            {children}
        </BaseItem>);
export default Item;