import React from 'react';
import QueueAnim from 'rc-queue-anim';
import {Row, Col, Divider} from 'antd';
import OverPack from 'rc-scroll-anim/lib/ScrollOverPack';
import {getChildrenToRender} from './utils';

class Teams3 extends React.PureComponent {
    getBlockChildren = (data) =>
        data.map((item, i) => {
            const {titleWrapper, image, ...$item} = item;
            return (
                <Col key={i.toString()} {...$item}>
                    <Row>
                        <Col span={7}>
                            <div {...image}>
                                <img src={image.children} alt="img"/>
                            </div>
                        </Col>
                        <Col span={17}>
                            <QueueAnim {...titleWrapper} type="bottom">
                                {titleWrapper.children.map(getChildrenToRender)}
                            </QueueAnim>
                        </Col>
                    </Row>
                </Col>
            );
        });

    getBlockTopChildren = (data) =>
        data.map((item, i) => {
            const {titleWrapper, ...$item} = item;
            return (
                <Col key={i.toString()} {...$item}>
                    {titleWrapper.children.map(getChildrenToRender)}
                </Col>
            );
        });

    render() {
        const {...props} = this.props;
        const {dataSource} = props;
        delete props.dataSource;
        delete props.isMobile;
        const listChildren = this.getBlockChildren(dataSource.block.children);
        const listTopChildren = this.getBlockTopChildren(
            dataSource.blockTop.children
        );
        return (
            <div {...props} {...dataSource.wrapper}>
                <div {...dataSource.page}>
                    <div {...dataSource.titleWrapper}>
                        {dataSource.titleWrapper.children.map(getChildrenToRender)}
                    </div>
                    <OverPack {...dataSource.OverPack}>
                        <QueueAnim type="bottom" key="tween" leaveReverse>
                            <QueueAnim
                                type="bottom"
                                key="blockTop"
                                {...dataSource.blockTop}
                                component={Row}
                            >
                                {listTopChildren}
                            </QueueAnim>
                            <div key="divider"><Divider key="divider"/></div>
                            <QueueAnim
                                type="bottom"
                                key="block"
                                {...dataSource.block}
                                component={Row}
                            >
                                {listChildren}
                            </QueueAnim>
                        </QueueAnim>
                    </OverPack>
                </div>
            </div>
        );
    }
}

export default Teams3;
